#!/usr/bin/env python3
"""Small, standard-library-only helpers for the Sloppy Jenkins batch files.

The public commands intentionally match the former Java helper:

    check-python
    check-java
    check-url <url> <settingName>
    agent-secret <agentName> <outFile>
    prompt-secret <outFile>
    new-job <path/name> <generic|gitlab> <repoUrl> [branch] [credentialId]
    gitlab-webhook <jobPath> <group/project>
    selftest

Credentials come only from environment variables or hidden prompts. They are
never accepted as command-line arguments and are scrubbed from error messages.
"""

import base64
import ctypes
import getpass
import http.client
import json
import os
from pathlib import Path
import re
import secrets
import socket
import ssl
import subprocess
import sys
from typing import Any, Dict, List, NamedTuple, Optional, Sequence, TextIO, Tuple
from urllib.parse import quote, urlencode, urlsplit, urlunsplit
import xml.etree.ElementTree as ET


EXIT_OK = 0
EXIT_ERROR = 1
EXIT_AUTH = 2
EXIT_UNREACHABLE = 3
EXIT_NOT_FOUND = 4
EXIT_AMBIGUOUS = 5

HOOK_NAME_PREFIX = "sloppy-jenkins:"
SECRETS: List[str] = []


class ToolError(Exception):
    """An expected failure whose message is safe to show after scrubbing."""

    def __init__(self, exit_code: int, message: str) -> None:
        super().__init__(message)
        self.exit_code = exit_code


class TransportError(Exception):
    """A network failure, including whether the request might have arrived."""

    def __init__(self, cause: BaseException, uncertain: bool) -> None:
        super().__init__(str(cause))
        self.cause = cause
        self.uncertain = uncertain


class Response(NamedTuple):
    status: int
    body: str
    headers: Any


# ---------------------------------------------------------------------------
# Settings, secrets, and prerequisites


def env(name: str) -> Optional[str]:
    value = os.environ.get(name)
    if value is None or not value.strip():
        return None
    return value.strip()


def jenkins_url() -> str:
    url = env("JENKINS_URL") or "http://localhost:8787/"
    return url if url.endswith("/") else url + "/"


def can_prompt(stream: Optional[TextIO] = None) -> bool:
    """Only a real terminal may receive a secret prompt; pipes and NUL fail closed."""

    input_stream = stream if stream is not None else sys.stdin
    try:
        if not input_stream.isatty():
            return False
    except (AttributeError, OSError):
        return False
    if os.name != "nt":
        return True

    # On Windows, isatty() reports True for the NUL device. GetConsoleMode only
    # succeeds for an actual console input handle, which is what getpass needs.
    try:
        import msvcrt

        handle = msvcrt.get_osfhandle(input_stream.fileno())
        mode = ctypes.c_ulong()
        get_console_mode = ctypes.WinDLL("kernel32", use_last_error=True).GetConsoleMode
        get_console_mode.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong)]
        get_console_mode.restype = ctypes.c_int
        return bool(get_console_mode(ctypes.c_void_p(handle), ctypes.byref(mode)))
    except (AttributeError, OSError, ValueError):
        return False


def hidden_secret(prompt: str, env_name: Optional[str] = None) -> str:
    value = env(env_name) if env_name else None
    if value is None:
        if not can_prompt():
            setting = env_name or "the secret"
            raise ToolError(
                EXIT_AUTH,
                "set %s (no interactive console to ask for it with hidden input)." % setting,
            )
        try:
            value = getpass.getpass(prompt).strip()
        except (EOFError, KeyboardInterrupt):
            raise ToolError(EXIT_AUTH, "%s is required." % (env_name or "the secret"))
        if not value:
            raise ToolError(EXIT_AUTH, "%s is required." % (env_name or "the secret"))
    SECRETS.append(value)
    return value


def jenkins_auth_header() -> str:
    require_safe_url(jenkins_url(), "JENKINS_URL")
    user = env("JENKINS_USER")
    if user is None:
        raise ToolError(
            EXIT_AUTH,
            "set JENKINS_USER to your Jenkins user name "
            "(the API token is asked for if JENKINS_API_TOKEN is not set).",
        )
    token = hidden_secret(
        "Jenkins API token for '%s' "
        "(Jenkins -> your user -> Security -> API Token; input is hidden): " % user,
        "JENKINS_API_TOKEN",
    )
    encoded = base64.b64encode((user + ":" + token).encode("utf-8")).decode("ascii")
    return "Basic " + encoded


def check_python() -> int:
    if sys.version_info < (3, 10):
        print(
            "ERROR: Python %d.%d found; Python 3.10 or newer is required."
            % (sys.version_info.major, sys.version_info.minor),
            file=sys.stderr,
        )
        return EXIT_ERROR
    print("Python %d.%d OK." % (sys.version_info.major, sys.version_info.minor))
    return EXIT_OK


def parse_java_major(output: str) -> Optional[int]:
    match = re.search(r'version\s+"([^"]+)"', output, flags=re.IGNORECASE)
    if not match:
        return None
    parts = match.group(1).split(".")
    try:
        return int(parts[1] if parts[0] == "1" and len(parts) > 1 else parts[0])
    except ValueError:
        return None


def check_java() -> int:
    try:
        completed = subprocess.run(
            ["java", "-version"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except FileNotFoundError:
        print(
            "ERROR: java was not found on PATH. Install Java 21 or newer, "
            "for example from https://adoptium.net/",
            file=sys.stderr,
        )
        return EXIT_ERROR
    output = (completed.stderr or "") + "\n" + (completed.stdout or "")
    major = parse_java_major(output)
    if completed.returncode != 0 or major is None:
        print("ERROR: could not determine the installed Java version.", file=sys.stderr)
        return EXIT_ERROR
    if major < 21:
        print("ERROR: Java %d found; Java 21 or newer is required." % major, file=sys.stderr)
        return EXIT_ERROR
    print("Java %d OK." % major)
    return EXIT_OK


def require_safe_url(url: str, setting: str) -> None:
    try:
        parsed = urlsplit(url)
        host = parsed.hostname
        # Accessing port also catches malformed values such as ':abc'.
        parsed.port
    except ValueError:
        raise ToolError(EXIT_ERROR, "%s is not a valid URL: %s" % (setting, url))
    scheme = parsed.scheme.lower()
    if scheme == "https" and host:
        return
    if scheme == "http" and is_loopback(host):
        return
    raise ToolError(
        EXIT_ERROR,
        "%s must use https:// (plain http:// is only allowed for localhost), got %s"
        % (setting, url),
    )


def is_loopback(host: Optional[str]) -> bool:
    if host is None:
        return False
    lowered = host.lower()
    return (
        lowered == "localhost"
        or lowered == "::1"
        or re.fullmatch(r"127(?:\.\d{1,3}){3}", lowered) is not None
    )


def scrub(text: Optional[str]) -> Optional[str]:
    if text is None:
        return None
    for secret in SECRETS:
        if secret and len(secret) >= 4:
            text = text.replace(secret, "***")
    return text


# ---------------------------------------------------------------------------
# HTTP. http.client does not follow redirects, and lets connect and read use
# separate timeouts. HTTPSConnection uses Python's normal certificate checks.


def http_request(
    method: str,
    url: str,
    body: Optional[str] = None,
    headers: Optional[Dict[str, str]] = None,
    read_timeout: int = 60,
) -> Response:
    try:
        parsed = urlsplit(url)
        host = parsed.hostname
        port = parsed.port
    except ValueError as exc:
        raise ToolError(EXIT_ERROR, "invalid URL: %s" % url) from exc
    if parsed.scheme not in ("http", "https") or not host:
        raise ToolError(EXIT_ERROR, "invalid URL: %s" % url)

    if parsed.scheme == "https":
        connection: http.client.HTTPConnection = http.client.HTTPSConnection(
            host, port=port, timeout=10, context=ssl.create_default_context()
        )
    else:
        connection = http.client.HTTPConnection(host, port=port, timeout=10)

    path = urlunsplit(("", "", parsed.path or "/", parsed.query, ""))
    connected = False
    try:
        try:
            connection.connect()
            connected = True
        except (OSError, ssl.SSLError, http.client.HTTPException) as exc:
            raise TransportError(exc, uncertain=False) from exc

        if connection.sock is not None:
            connection.sock.settimeout(read_timeout)
        data = body.encode("utf-8") if body is not None else None
        try:
            connection.request(method, path, body=data, headers=headers or {})
            response = connection.getresponse()
            raw = response.read()
        except (OSError, ssl.SSLError, http.client.HTTPException) as exc:
            raise TransportError(exc, uncertain=connected) from exc
        return Response(response.status, raw.decode("utf-8", errors="replace"), response.headers)
    finally:
        connection.close()


def send(
    method: str,
    url: str,
    what: str,
    body: Optional[str] = None,
    headers: Optional[Dict[str, str]] = None,
    timeout: int = 60,
) -> Response:
    try:
        return http_request(method, url, body, headers, timeout)
    except TransportError as exc:
        name = type(exc.cause).__name__
        if not exc.uncertain:
            parsed = urlsplit(url)
            raise ToolError(
                EXIT_UNREACHABLE,
                "%s is not reachable at %s://%s (is it running?)"
                % (what, parsed.scheme, parsed.netloc),
            )
        raise ToolError(EXIT_UNREACHABLE, "%s request failed: %s" % (what, name))


def jenkins(
    method: str, relative_path: str, body: Optional[str], auth: str
) -> Response:
    headers = {"Authorization": auth}
    if body is not None:
        headers["Content-Type"] = "application/xml; charset=UTF-8"
    response = send(
        method,
        jenkins_url() + relative_path,
        "Jenkins",
        body=body,
        headers=headers,
        timeout=60,
    )
    if response.status in (401, 403):
        raise ToolError(
            EXIT_AUTH,
            "Jenkins rejected the credentials or permissions (HTTP %d) for %s"
            % (response.status, relative_path),
        )
    return response


# ---------------------------------------------------------------------------
# Jenkins item paths and small formatting helpers


def split_path(item_path: str) -> List[str]:
    return [segment.strip() for segment in item_path.split("/") if segment.strip()]


def job_url_path(item_path: str) -> str:
    return "".join("job/%s/" % quote(segment, safe="") for segment in split_path(item_path))


def project_url_path(item_path: str) -> str:
    return "/".join(quote(segment, safe="") for segment in split_path(item_path))


def encode_query(value: str) -> str:
    return quote(value, safe="")


def snippet(body: Optional[str]) -> str:
    if body is None:
        return ""
    plain = re.sub(r"<[^>]+>", " ", body)
    plain = re.sub(r"\s+", " ", plain).strip()
    return scrub(plain[:200] + ("..." if len(plain) > 200 else "")) or ""


# ---------------------------------------------------------------------------
# XML. ElementTree does not load external entities, and DOCTYPE is explicitly
# rejected to retain the Java helper's stronger, easy-to-audit rule. Expat is
# an XML 1.0 parser, so XML 1.1-only control references are hidden behind a
# unique legal placeholder while parsing and restored when the XML is written.


XML11_MARKER_ATTR = "_sloppy_xml11_placeholder_prefix"
XML11_DECLARATION = re.compile(
    r"^\s*<\?xml\s+[^>]*version\s*=\s*['\"]1\.1['\"]",
    flags=re.IGNORECASE,
)
XML_CHARACTER_REFERENCE = re.compile(
    r"&#(?:(?:x|X)([0-9A-Fa-f]+)|([0-9]+));"
)


def is_xml11_restricted_character(codepoint: int) -> bool:
    return (
        0x01 <= codepoint <= 0x08
        or 0x0B <= codepoint <= 0x0C
        or 0x0E <= codepoint <= 0x1F
        or 0x7F <= codepoint <= 0x84
        or 0x86 <= codepoint <= 0x9F
    )


def protect_xml11_references(xml_text: str) -> Tuple[str, Optional[str]]:
    if XML11_DECLARATION.search(xml_text) is None:
        return xml_text, None
    prefix = "__SLOPPY_XML11_%s_" % secrets.token_hex(12).upper()
    while prefix in xml_text:
        prefix = "__SLOPPY_XML11_%s_" % secrets.token_hex(12).upper()
    changed = False

    def replace_reference(match: re.Match) -> str:
        nonlocal changed
        codepoint = int(match.group(1), 16) if match.group(1) else int(match.group(2))
        if not is_xml11_restricted_character(codepoint):
            return match.group(0)
        changed = True
        return "%s%X__" % (prefix, codepoint)

    protected = XML_CHARACTER_REFERENCE.sub(replace_reference, xml_text)
    return (protected, prefix) if changed else (xml_text, None)


def parse_xml(xml_text: str) -> ET.Element:
    if "<!DOCTYPE" in xml_text.upper():
        raise ToolError(EXIT_ERROR, "XML documents containing DOCTYPE are not allowed.")
    protected, placeholder_prefix = protect_xml11_references(xml_text)
    try:
        root = ET.fromstring(protected)
    except ET.ParseError as exc:
        raise ToolError(EXIT_ERROR, "invalid XML: %s" % exc) from exc
    if placeholder_prefix is not None:
        if XML11_MARKER_ATTR in root.attrib:
            raise ToolError(
                EXIT_ERROR,
                "XML root uses a reserved Sloppy Jenkins helper attribute.",
            )
        root.set(XML11_MARKER_ATTR, placeholder_prefix)
    return root


def to_xml(root: ET.Element) -> str:
    placeholder_prefix = root.attrib.pop(XML11_MARKER_ATTR, None)
    try:
        xml_text = ET.tostring(
            root, encoding="utf-8", xml_declaration=True
        ).decode("utf-8")
    finally:
        if placeholder_prefix is not None:
            root.set(XML11_MARKER_ATTR, placeholder_prefix)
    # Jenkins writes config.xml as XML 1.1. Keep that declaration, especially
    # when the document contains a restored XML 1.1-only character reference.
    # Raw NEL and line-separator characters are XML 1.1 line endings, so use
    # references to prevent a conforming parser from normalizing them to LF.
    xml_text = xml_text.replace("version='1.0'", "version='1.1'", 1)
    xml_text = xml_text.replace("\u0085", "&#x85;").replace("\u2028", "&#x2028;")
    if placeholder_prefix is not None:
        pattern = re.compile(re.escape(placeholder_prefix) + r"([0-9A-F]+)__")
        xml_text = pattern.sub(lambda match: "&#x%s;" % match.group(1), xml_text)
    return xml_text


def first_element(root: ET.Element, tag: str) -> Optional[ET.Element]:
    return next((element for element in root.iter(tag)), None)


def set_child_text(parent: ET.Element, tag: str, text: str) -> None:
    for child in list(parent):
        if child.tag == tag:
            child.text = text
            return
    ET.SubElement(parent, tag).text = text


def child_text(parent: ET.Element, tag: str) -> Optional[str]:
    for child in list(parent):
        if child.tag == tag:
            return child.text or ""
    return None


# ---------------------------------------------------------------------------
# Agent secret


def extract_agent_secret(jnlp_xml: str) -> str:
    root = parse_xml(jnlp_xml)
    argument = first_element(root, "argument")
    if argument is None:
        raise ToolError(EXIT_ERROR, "the agent JNLP file has no secret argument.")
    secret = (argument.text or "").strip()
    if re.fullmatch(r"[0-9a-fA-F]{32,}", secret) is None:
        raise ToolError(
            EXIT_ERROR,
            "the agent JNLP file did not contain a secret in the expected format.",
        )
    return secret


def write_secret_file(out_file: Path, secret: str) -> None:
    out_file.absolute().parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(secret, encoding="utf-8")


def agent_secret(agent_name: str, out_file: Path) -> int:
    auth = jenkins_auth_header()
    response = jenkins(
        "GET",
        "computer/%s/jenkins-agent.jnlp" % quote(agent_name, safe=""),
        None,
        auth,
    )
    if response.status == 404:
        raise ToolError(EXIT_NOT_FOUND, "Jenkins has no node named '%s'." % agent_name)
    if response.status != 200:
        raise ToolError(
            EXIT_ERROR,
            "could not read the agent secret (HTTP %d)." % response.status,
        )
    secret = extract_agent_secret(response.body)
    SECRETS.append(secret)
    write_secret_file(out_file, secret)
    print("Agent secret for '%s' saved to %s." % (agent_name, out_file))
    return EXIT_OK


def prompt_secret(out_file: Path) -> int:
    if not can_prompt():
        raise ToolError(
            EXIT_ERROR,
            "the agent secret can only be pasted in an interactive Command Prompt window, "
            "where the input is hidden. Run start-agent.bat from Command Prompt, or set "
            "JENKINS_USER so the secret is fetched from Jenkins. Nothing saved.",
        )
    try:
        secret = getpass.getpass(
            "Paste the agent secret (input is hidden) and press Enter: "
        ).strip()
    except (EOFError, KeyboardInterrupt):
        raise ToolError(EXIT_ERROR, "the agent secret is required. Nothing saved.")
    if re.fullmatch(r"[0-9a-fA-F]{32,}", secret) is None:
        raise ToolError(
            EXIT_ERROR,
            "that does not look like a Jenkins agent secret "
            "(a long hexadecimal string). Nothing saved.",
        )
    SECRETS.append(secret)
    write_secret_file(out_file, secret)
    print("Agent secret saved to %s." % out_file)
    return EXIT_OK


# ---------------------------------------------------------------------------
# Create a job from one of the managed templates


def template_for(kind: str) -> str:
    lowered = kind.lower()
    if lowered == "generic":
        return "Templates/pipeline-from-scm"
    if lowered == "gitlab":
        return "Templates/gitlab-pipeline-from-scm"
    raise ToolError(EXIT_ERROR, "template must be 'generic' or 'gitlab', got '%s'." % kind)


def configure_job_xml(
    template_xml: str,
    repo_url: str,
    branch: str,
    credential_id: Optional[str],
    template: str,
) -> str:
    root = parse_xml(template_xml)
    remote = first_element(root, "hudson.plugins.git.UserRemoteConfig")
    branch_spec = first_element(root, "hudson.plugins.git.BranchSpec")
    if remote is None or branch_spec is None:
        raise ToolError(EXIT_ERROR, "template has no Git repository/branch section.")
    set_child_text(remote, "url", repo_url)
    if credential_id is not None and credential_id.strip():
        set_child_text(remote, "credentialsId", credential_id)
    spec = branch if branch.startswith("*/") or branch.startswith("refs/") or "*" in branch else "*/" + branch
    set_child_text(branch_spec, "name", spec)
    set_child_text(root, "disabled", "false")
    set_child_text(root, "description", "Created from %s by tools\\new-job.bat." % template)
    return to_xml(root)


def new_job(
    path: str,
    kind: str,
    repo_url: str,
    branch: str,
    credential_id: Optional[str],
) -> int:
    auth = jenkins_auth_header()
    segments = split_path(path)
    if not segments:
        raise ToolError(EXIT_ERROR, "job name is empty.")
    leaf = segments[-1]
    parent = "/".join(segments[:-1])
    template = template_for(kind)

    if jenkins("GET", job_url_path(path) + "api/json?tree=name", None, auth).status == 200:
        raise ToolError(EXIT_ERROR, "job '%s' already exists; nothing changed." % path)
    if parent and jenkins(
        "GET", job_url_path(parent) + "api/json?tree=name", None, auth
    ).status != 200:
        raise ToolError(
            EXIT_NOT_FOUND,
            "folder '%s' does not exist. Create it in Jenkins first (New Item -> Folder)."
            % parent,
        )

    template_response = jenkins("GET", job_url_path(template) + "config.xml", None, auth)
    if template_response.status == 404:
        raise ToolError(
            EXIT_NOT_FOUND,
            "template '%s' not found. Is the Sloppy Jenkins image up to date?" % template,
        )
    if template_response.status != 200:
        raise ToolError(
            EXIT_ERROR,
            "could not read template '%s' (HTTP %d)."
            % (template, template_response.status),
        )

    xml = configure_job_xml(
        template_response.body, repo_url, branch, credential_id, template
    )
    created = jenkins(
        "POST",
        job_url_path(parent) + "createItem?name=" + encode_query(leaf),
        xml,
        auth,
    )
    if created.status != 200:
        raise ToolError(
            EXIT_ERROR,
            "Jenkins refused to create '%s' (HTTP %d): %s"
            % (path, created.status, snippet(created.body)),
        )
    print(
        "Created job '%s' from %s: %s%s"
        % (path, template, jenkins_url(), job_url_path(path))
    )
    if credential_id is None:
        print(
            "Credential ID left as 'scm-credentials'; create it in Manage Jenkins -> "
            "Credentials or pick another in the job."
        )
    if kind.lower() == "gitlab":
        print(
            "GitLab trigger has no secret yet: run tools\\gitlab-webhook.bat or "
            "generate one in the job's trigger settings."
        )
    return EXIT_OK


# ---------------------------------------------------------------------------
# GitLab webhook synchronization


class HookChoice(NamedTuple):
    action: str
    hook: Optional[Dict[str, Any]]
    candidates: List[Dict[str, Any]]


def as_id(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(int(value))
    return str(value)


def choose_hook(
    hooks: Sequence[Any], hook_name: str, job_path: str
) -> HookChoice:
    by_name: List[Dict[str, Any]] = []
    by_url: List[Dict[str, Any]] = []
    raw_suffix = "/project/" + "/".join(split_path(job_path))
    encoded_suffix = "/project/" + project_url_path(job_path)
    for item in hooks:
        if not isinstance(item, dict):
            continue
        if item.get("name") == hook_name:
            by_name.append(item)
        url = str(item.get("url"))
        while url.endswith("/"):
            url = url[:-1]
        if url.endswith(raw_suffix) or url.endswith(encoded_suffix):
            by_url.append(item)
    pool = by_name if by_name else by_url
    if not pool:
        return HookChoice("CREATE", None, [])
    if len(pool) == 1:
        return HookChoice("UPDATE", pool[0], [])
    return HookChoice("AMBIGUOUS", None, pool)


def gitlab_list_hooks(hooks_url: str, token: str) -> List[Any]:
    all_hooks: List[Any] = []
    for page in range(1, 21):
        response = send(
            "GET",
            "%s?per_page=100&page=%d" % (hooks_url, page),
            "GitLab",
            headers={"PRIVATE-TOKEN": token},
            timeout=30,
        )
        if response.status in (401, 403):
            raise ToolError(
                EXIT_AUTH,
                "GitLab rejected the token (HTTP %d). It needs 'api' scope and "
                "Maintainer on the project. Nothing changed." % response.status,
            )
        if response.status == 404:
            raise ToolError(
                EXIT_NOT_FOUND,
                "GitLab project not found or not visible to this token. Nothing changed.",
            )
        if response.status != 200:
            raise ToolError(
                EXIT_ERROR,
                "GitLab hook list failed (HTTP %d): %s. Nothing changed."
                % (response.status, snippet(response.body)),
            )
        try:
            parsed = json.loads(response.body)
        except json.JSONDecodeError as exc:
            raise ToolError(
                EXIT_ERROR, "unexpected GitLab response for the hook list. Nothing changed."
            ) from exc
        if not isinstance(parsed, list):
            raise ToolError(
                EXIT_ERROR, "unexpected GitLab response for the hook list. Nothing changed."
            )
        all_hooks.extend(parsed)
        if len(parsed) < 100:
            break
    return all_hooks


def choose_ngrok_tunnel(data: Any, jenkins_port: int) -> str:
    if not isinstance(data, dict) or not isinstance(data.get("tunnels"), list):
        raise ToolError(
            EXIT_ERROR, "unexpected ngrok API response. Set NGROK_URL instead."
        )
    https_urls: List[str] = []
    matching: List[str] = []
    for item in data["tunnels"]:
        if not isinstance(item, dict):
            continue
        public_url = str(item.get("public_url"))
        if not public_url.startswith("https://"):
            continue
        https_urls.append(public_url)
        config = item.get("config")
        address = str(config.get("addr")) if isinstance(config, dict) else ""
        if address.endswith(":" + str(jenkins_port)) or address == str(jenkins_port):
            matching.append(public_url)
    if len(matching) == 1:
        return matching[0]
    if not matching and len(https_urls) == 1:
        return https_urls[0]
    if not https_urls:
        raise ToolError(
            EXIT_UNREACHABLE,
            "ngrok has no https tunnel. Run: ngrok http %d  (or set NGROK_URL)."
            % jenkins_port,
        )
    choices = matching if matching else https_urls
    raise ToolError(
        EXIT_AMBIGUOUS,
        "several ngrok tunnels found %s; set NGROK_URL." % choices,
    )


def public_jenkins_url() -> str:
    url = env("NGROK_URL")
    if url is None:
        response = send(
            "GET",
            "http://127.0.0.1:4040/api/tunnels",
            "ngrok (local API on 127.0.0.1:4040)",
            timeout=5,
        )
        if response.status != 200:
            raise ToolError(
                EXIT_UNREACHABLE,
                "ngrok local API answered HTTP %d. Start ngrok or set NGROK_URL."
                % response.status,
            )
        try:
            tunnel_data = json.loads(response.body)
        except json.JSONDecodeError as exc:
            raise ToolError(
                EXIT_ERROR, "unexpected ngrok API response. Set NGROK_URL instead."
            ) from exc
        parsed_jenkins = urlsplit(jenkins_url())
        url = choose_ngrok_tunnel(tunnel_data, parsed_jenkins.port or 80)
    url = url.rstrip("/")
    if not url.startswith("https://"):
        raise ToolError(
            EXIT_ERROR,
            "the public Jenkins URL must start with https:// (got %s)." % url,
        )
    return url


def restore_jenkins(job_path: str, backup_xml: str, auth: str, reason: str) -> None:
    try:
        response = jenkins(
            "POST", job_url_path(job_path) + "config.xml", backup_xml, auth
        )
        restored = "ok" if response.status == 200 else "HTTP %d" % response.status
    except ToolError as exc:
        restored = str(exc)
    if restored == "ok":
        print(
            "ERROR: %s; Jenkins restored to its previous secret. "
            "Rerun the helper once the problem is fixed." % scrub(reason),
            file=sys.stderr,
        )
    else:
        print(
            "ERROR: %s. Restoring Jenkins ALSO failed (%s):"
            % (scrub(reason), scrub(restored)),
            file=sys.stderr,
        )
        print(
            "Jenkins has the new secret, GitLab does not. "
            "Rerun the helper to resynchronise both sides.",
            file=sys.stderr,
        )


def gitlab_webhook(job_path: str, project: str) -> int:
    auth = jenkins_auth_header()
    gitlab_url = (env("GITLAB_URL") or "https://gitlab.com").rstrip("/")
    require_safe_url(gitlab_url, "GITLAB_URL")
    gitlab_token = hidden_secret(
        "GitLab personal access token ('api' scope, Maintainer on the project; "
        "input is hidden): ",
        "GITLAB_TOKEN",
    )
    hooks_url = "%s/api/v4/projects/%s/hooks" % (
        gitlab_url,
        encode_query(project),
    )
    hook_url = public_jenkins_url() + "/project/" + project_url_path(job_path)
    hook_name = HOOK_NAME_PREFIX + "/".join(split_path(job_path))

    config_response = jenkins(
        "GET", job_url_path(job_path) + "config.xml", None, auth
    )
    if config_response.status == 404:
        raise ToolError(EXIT_NOT_FOUND, "Jenkins job '%s' not found." % job_path)
    if config_response.status != 200:
        raise ToolError(
            EXIT_ERROR,
            "could not read job '%s' (HTTP %d)."
            % (job_path, config_response.status),
        )
    backup_xml = config_response.body
    job_root = parse_xml(backup_xml)
    trigger = first_element(
        job_root, "com.dabsquared.gitlabjenkins.GitLabPushTrigger"
    )
    if trigger is None:
        raise ToolError(
            EXIT_ERROR,
            "job '%s' has no GitLab trigger. Create it from "
            "Templates/gitlab-pipeline-from-scm." % job_path,
        )

    hooks = gitlab_list_hooks(hooks_url, gitlab_token)
    choice = choose_hook(hooks, hook_name, job_path)
    if choice.action == "AMBIGUOUS":
        lines = [
            "several GitLab hooks match job '%s'; nothing changed. Remove the extra "
            "ones in GitLab (Settings -> Webhooks) and rerun:" % job_path
        ]
        for hook in choice.candidates:
            lines.append(
                "  hook %s  %s" % (as_id(hook.get("id")), scrub(str(hook.get("url"))))
            )
        raise ToolError(EXIT_AMBIGUOUS, "\n".join(lines))

    secret = secrets.token_hex(24)
    SECRETS.append(secret)
    set_child_text(trigger, "secretToken", secret)
    updated = jenkins(
        "POST", job_url_path(job_path) + "config.xml", to_xml(job_root), auth
    )
    if updated.status != 200:
        raise ToolError(
            EXIT_ERROR,
            "Jenkins refused the job update (HTTP %d): %s. Nothing changed in GitLab."
            % (updated.status, snippet(updated.body)),
        )

    form = {
        "url": hook_url,
        "name": hook_name,
        "description": "Managed by Sloppy Jenkins (tools\\gitlab-webhook.bat)",
        "token": secret,
        "push_events": "true",
        "merge_requests_events": "true",
        "note_events": "true",
        "enable_ssl_verification": "true",
    }
    method = "PUT" if choice.action == "UPDATE" else "POST"
    target = (
        hooks_url + "/" + as_id(choice.hook.get("id"))
        if choice.action == "UPDATE" and choice.hook is not None
        else hooks_url
    )
    try:
        gitlab_response = http_request(
            method,
            target,
            body=urlencode(form),
            headers={
                "PRIVATE-TOKEN": gitlab_token,
                "Content-Type": "application/x-www-form-urlencoded",
            },
            read_timeout=30,
        )
    except TransportError as exc:
        name = type(exc.cause).__name__
        if exc.uncertain:
            restore_jenkins(
                job_path,
                backup_xml,
                auth,
                "GitLab result unknown (%s)" % name,
            )
            print(
                "GitLab may have applied the change. "
                "Rerun the helper to resynchronise both sides.",
                file=sys.stderr,
            )
        else:
            restore_jenkins(
                job_path,
                backup_xml,
                auth,
                "GitLab is not reachable (%s)" % name,
            )
        return EXIT_UNREACHABLE

    if gitlab_response.status not in (200, 201):
        restore_jenkins(
            job_path,
            backup_xml,
            auth,
            "GitLab update failed (HTTP %d: %s)"
            % (gitlab_response.status, snippet(gitlab_response.body)),
        )
        return (
            EXIT_AUTH
            if gitlab_response.status in (401, 403)
            else EXIT_ERROR
        )

    try:
        created = json.loads(gitlab_response.body)
    except json.JSONDecodeError:
        created = {}
    hook_id = as_id(created.get("id")) if isinstance(created, dict) else "?"
    verb = "created" if method == "POST" else "updated"
    print("Job '%s': GitLab hook %s %s -> %s" % (job_path, hook_id, verb, hook_url))
    return EXIT_OK


# ---------------------------------------------------------------------------
# Offline self-test


def selftest() -> int:
    passes = 0
    failures = 0

    def check(name: str, condition: bool) -> None:
        nonlocal passes, failures
        if condition:
            passes += 1
        else:
            failures += 1
            print("FAIL: " + name)

    def safe(url: str) -> bool:
        try:
            require_safe_url(url, "URL")
            return True
        except ToolError:
            return False

    check("python version", sys.version_info >= (3, 10))
    check("java version 21", parse_java_major('openjdk version "21.0.11"') == 21)
    check("legacy java version", parse_java_major('java version "1.8.0_401"') == 8)
    check("bad java version", parse_java_major("not a version") is None)

    check("jobUrlPath simple", job_url_path("powerprof") == "job/powerprof/")
    check(
        "jobUrlPath folder+space",
        job_url_path("Team A/my job") == "job/Team%20A/job/my%20job/",
    )
    check("jobUrlPath trims slashes", job_url_path("/a//b/") == "job/a/job/b/")
    check("projectUrlPath", project_url_path("Team A/my job") == "Team%20A/my%20job")
    check("query encoding", encode_query("group/sub/project") == "group%2Fsub%2Fproject")

    hooks = [
        {"id": 1, "url": "https://old.ngrok-free.dev/project/other", "name": None},
        {
            "id": 2,
            "url": "https://old.ngrok-free.dev/project/myjob",
            "name": "sloppy-jenkins:myjob",
        },
        {"id": 3, "url": "https://elsewhere.example/project/myjob/", "name": None},
    ]
    choice = choose_hook(hooks, "sloppy-jenkins:myjob", "myjob")
    check(
        "hook by name wins over url",
        choice.action == "UPDATE" and choice.hook is not None and as_id(choice.hook.get("id")) == "2",
    )
    choice = choose_hook(
        [{"id": 7, "url": "https://a.example/project/Team%20A/my%20job"}],
        "sloppy-jenkins:Team A/my job",
        "Team A/my job",
    )
    check(
        "hook adopted by single url match",
        choice.action == "UPDATE" and choice.hook is not None and as_id(choice.hook.get("id")) == "7",
    )
    choice = choose_hook(
        [
            {"id": 8, "url": "https://a.example/project/myjob"},
            {"id": 9, "url": "https://b.example/project/myjob"},
        ],
        "sloppy-jenkins:myjob",
        "myjob",
    )
    check("hook ambiguity on two url matches", choice.action == "AMBIGUOUS" and len(choice.candidates) == 2)
    choice = choose_hook(
        [
            {"id": 10, "url": "https://a.example/x", "name": "sloppy-jenkins:myjob"},
            {"id": 11, "url": "https://b.example/y", "name": "sloppy-jenkins:myjob"},
        ],
        "sloppy-jenkins:myjob",
        "myjob",
    )
    check("hook ambiguity on two name matches", choice.action == "AMBIGUOUS")
    check(
        "hook suffix must match whole job",
        choose_hook(
            [{"id": 1, "url": "https://a.example/project/myjob2"}],
            "sloppy-jenkins:myjob",
            "myjob",
        ).action
        == "CREATE",
    )
    check("hook create on empty list", choose_hook([], "n", "j").action == "CREATE")

    tunnels = {
        "tunnels": [
            {
                "public_url": "https://jenkins.ngrok-free.dev",
                "proto": "https",
                "config": {"addr": "http://localhost:8787"},
            },
            {
                "public_url": "https://other.ngrok-free.dev",
                "proto": "https",
                "config": {"addr": "http://localhost:3000"},
            },
        ]
    }
    check(
        "ngrok picks jenkins port",
        choose_ngrok_tunnel(tunnels, 8787) == "https://jenkins.ngrok-free.dev",
    )
    check(
        "ngrok single https fallback",
        choose_ngrok_tunnel(
            {
                "tunnels": [
                    {
                        "public_url": "https://x.dev",
                        "config": {"addr": "http://localhost:9999"},
                    }
                ]
            },
            8787,
        )
        == "https://x.dev",
    )
    try:
        choose_ngrok_tunnel(tunnels, 1234)
        ambiguous = False
    except ToolError as exc:
        ambiguous = exc.exit_code == EXIT_AMBIGUOUS
    check("ngrok ambiguity", ambiguous)
    try:
        choose_ngrok_tunnel({"tunnels": []}, 8787)
        none = False
    except ToolError as exc:
        none = exc.exit_code == EXIT_UNREACHABLE
    check("ngrok none", none)

    template = (
        "<?xml version='1.1' encoding='UTF-8'?><flow-definition><description>TEMPLATE</description>"
        "<properties><org.jenkinsci.plugins.workflow.job.properties.PipelineTriggersJobProperty><triggers>"
        "<com.dabsquared.gitlabjenkins.GitLabPushTrigger><secretToken></secretToken>"
        "</com.dabsquared.gitlabjenkins.GitLabPushTrigger></triggers>"
        "</org.jenkinsci.plugins.workflow.job.properties.PipelineTriggersJobProperty></properties>"
        "<definition><scm><userRemoteConfigs><hudson.plugins.git.UserRemoteConfig>"
        "<url>https://example.invalid/YOUR/REPO.git</url><credentialsId>scm-credentials</credentialsId>"
        "</hudson.plugins.git.UserRemoteConfig></userRemoteConfigs><branches>"
        "<hudson.plugins.git.BranchSpec><name>*/main</name></hudson.plugins.git.BranchSpec>"
        "</branches></scm></definition><disabled>true</disabled></flow-definition>"
    )
    configured = parse_xml(
        configure_job_xml(
            template,
            "https://gitlab.com/g/p.git?a=1&b=<2>",
            "dev",
            "my-cred",
            "Templates/x",
        )
    )
    remote = first_element(configured, "hudson.plugins.git.UserRemoteConfig")
    branch_spec = first_element(configured, "hudson.plugins.git.BranchSpec")
    check("xml url escaped round trip", remote is not None and child_text(remote, "url") == "https://gitlab.com/g/p.git?a=1&b=<2>")
    check("xml credential", remote is not None and child_text(remote, "credentialsId") == "my-cred")
    check("xml branch prefixed", branch_spec is not None and child_text(branch_spec, "name") == "*/dev")
    check("xml enabled", child_text(configured, "disabled") == "false")
    configured = parse_xml(configure_job_xml(template, "u", "refs/tags/v1", None, "Templates/x"))
    remote = first_element(configured, "hudson.plugins.git.UserRemoteConfig")
    branch_spec = first_element(configured, "hudson.plugins.git.BranchSpec")
    check("xml credential kept when omitted", remote is not None and child_text(remote, "credentialsId") == "scm-credentials")
    check("xml branch refs kept", branch_spec is not None and child_text(branch_spec, "name") == "refs/tags/v1")
    trigger = first_element(configured, "com.dabsquared.gitlabjenkins.GitLabPushTrigger")
    if trigger is not None:
        set_child_text(trigger, "secretToken", "abc123")
    round_trip = parse_xml(to_xml(configured))
    trigger = first_element(round_trip, "com.dabsquared.gitlabjenkins.GitLabPushTrigger")
    check("xml secretToken set", trigger is not None and child_text(trigger, "secretToken") == "abc123")
    try:
        parse_xml("<?xml version='1.0'?><!DOCTYPE x [<!ENTITY e SYSTEM 'file:///etc/passwd'>]><x>&e;</x>")
        doctype_rejected = False
    except ToolError:
        doctype_rejected = True
    check("xml rejects DOCTYPE", doctype_rejected)
    xml11_control = parse_xml(
        "<?xml version='1.1' encoding='UTF-8'?><flow-definition>"
        "<script>before&#x1b;after&#27;</script></flow-definition>"
    )
    xml11_output = to_xml(xml11_control)
    check(
        "xml11 control references preserved",
        xml11_output.count("&#x1B;") == 2
        and "_sloppy_xml11_placeholder_prefix" not in xml11_output,
    )
    check("xml11 declaration preserved", "version='1.1'" in xml11_output)
    xml11_line_endings = parse_xml(
        "<?xml version='1.1' encoding='UTF-8'?><flow-definition>"
        "<description>line\u2028sep | nel\u0085end</description></flow-definition>"
    )
    xml11_line_output = to_xml(xml11_line_endings)
    xml11_line_round_trip = parse_xml(xml11_line_output)
    description = first_element(xml11_line_round_trip, "description")
    check(
        "xml11 NEL and line separator preserved",
        "&#x85;" in xml11_line_output
        and "&#x2028;" in xml11_line_output
        and "\u0085" not in xml11_line_output
        and "\u2028" not in xml11_line_output
        and description is not None
        and description.text == "line\u2028sep | nel\u0085end",
    )

    jnlp = "<jnlp><application-desc><argument>%s</argument><argument>windows_build_agent</argument></application-desc></jnlp>" % ("a" * 64)
    check("jnlp secret", extract_agent_secret(jnlp) == "a" * 64)
    first_secret = secrets.token_hex(24)
    check("secret length/hex", re.fullmatch(r"[0-9a-f]{48}", first_secret) is not None and first_secret != secrets.token_hex(24))
    SECRETS.append("topsecretvalue")
    check("scrub", scrub("x topsecretvalue y") == "x *** y")
    check(
        "form encoding",
        urlencode({"url": "https://a.dev/project/j", "token": "a&b"})
        == "url=https%3A%2F%2Fa.dev%2Fproject%2Fj&token=a%26b",
    )

    check("https allowed", safe("https://gitlab.com"))
    check("http localhost allowed", safe("http://localhost:8787/"))
    check("http 127.x allowed", safe("http://127.0.0.1:18929"))
    check("http ::1 allowed", safe("http://[::1]:8787/"))
    check("http remote rejected", not safe("http://gitlab.example.com"))
    check("http lookalike rejected", not safe("http://localhost.evil.example/"))
    check("http 127 prefix lookalike rejected", not safe("http://127.0.0.1.evil.example/"))
    check("ftp rejected", not safe("ftp://localhost/"))

    class NotATerminal:
        @staticmethod
        def isatty() -> bool:
            return False

    check("noninteractive prompt refused", not can_prompt(NotATerminal()))
    with open(os.devnull, "r", encoding="utf-8") as null_input:
        check("null-device prompt refused", not can_prompt(null_input))

    print("selftest: %d passed, %d failed" % (passes, failures))
    return EXIT_OK if failures == 0 else EXIT_ERROR


# ---------------------------------------------------------------------------
# Command dispatch


def require_args(args: Sequence[str], minimum: int, usage_text: str) -> None:
    if len(args) < minimum:
        raise ToolError(EXIT_ERROR, "usage: " + usage_text)
    for argument in args:
        if '"' in argument or "\n" in argument or "\r" in argument:
            raise ToolError(EXIT_ERROR, "arguments must not contain quotes or line breaks")


def usage() -> None:
    print(
        "Usage: python sloppy_tool.py check-python | check-java | "
        "check-url <url> <settingName> |",
        file=sys.stderr,
    )
    print(
        "       agent-secret <agentName> <outFile> | prompt-secret <outFile> |",
        file=sys.stderr,
    )
    print(
        "       new-job <path/name> <generic|gitlab> <repoUrl> [branch] "
        "[credentialId] |",
        file=sys.stderr,
    )
    print("       gitlab-webhook <jobPath> <group/project> | selftest", file=sys.stderr)


def run(args: Sequence[str]) -> int:
    if not args:
        usage()
        return EXIT_ERROR
    command = args[0]
    if command == "check-python":
        return check_python()
    if command == "check-java":
        return check_java()
    if command == "check-url":
        require_args(args, 3, "check-url <url> <settingName>")
        require_safe_url(args[1], args[2])
        return EXIT_OK
    if command == "agent-secret":
        require_args(args, 3, "agent-secret <agentName> <outFile>")
        return agent_secret(args[1], Path(args[2]))
    if command == "prompt-secret":
        require_args(args, 2, "prompt-secret <outFile>")
        return prompt_secret(Path(args[1]))
    if command == "new-job":
        require_args(
            args,
            4,
            "new-job <path/name> <generic|gitlab> <repoUrl> [branch] [credentialId]",
        )
        return new_job(
            args[1],
            args[2],
            args[3],
            args[4] if len(args) > 4 else "main",
            args[5] if len(args) > 5 else None,
        )
    if command == "gitlab-webhook":
        require_args(args, 3, "gitlab-webhook <jobPath> <group/project>")
        return gitlab_webhook(args[1], args[2])
    if command == "selftest":
        return selftest()
    usage()
    return EXIT_ERROR


def main() -> int:
    try:
        return run(sys.argv[1:])
    except KeyboardInterrupt:
        print("\nCancelled.", file=sys.stderr)
        return 130
    except ToolError as exc:
        print("ERROR: " + (scrub(str(exc)) or ""), file=sys.stderr)
        return exc.exit_code
    except Exception as exc:  # Unexpected bugs still get a concise, scrubbed report.
        print(
            "ERROR: %s: %s" % (type(exc).__name__, scrub(str(exc)) or ""),
            file=sys.stderr,
        )
        return EXIT_ERROR


if __name__ == "__main__":
    sys.exit(main())
