# Troubleshooting

Problems actually hit while building,  upgrading source, and testing Sloppy Jenkins with what causes/resolves.

**Contents**
- [Jenkins container and startup](#jenkins-container-and-startup)
- [Admin login](#admin-login)
- [Credentials from .env](#credentials-from-env)
- [Optional SSH build node](#optional-ssh-build-node)
- [Windows build agent](#windows-build-agent)
- [Helper scripts in tools\\](#helper-scripts-in-tools)
- [Job templates](#job-templates)
- [GitLab webhooks and ngrok](#gitlab-webhooks-and-ngrok)
- [Other issues](#other-issues)

---

## Jenkins container and startup

### The first start takes 10 minutes or more
**Symptom:** `docker compose up -d` returns quickly, but http://localhost:8787 doesn't answer for a long time. The logs stop at `Started initialization` for minutes.

**Cause:** on the first start with an empty `jenkins_home`, Jenkins unpacks about 200 plugins into `C:\MNT\docker\jenkins\jenkins_home\plugins`. File access from a Linux container to a Windows folder is slow.

**Fix:** wait. Watch progress with `docker compose logs -f` until you see `Jenkins is fully up and running`. Later starts are much faster. Recent upgrades to this project made it faster (found aproblem that init-groovy.d scripts kept running at each instance run)

### A script I put in jenkins_home\init.groovy.d disappeared
**Cause:** the project owns that folder. On every container start it is deleted and refilled from `init-scripts\` (`PRE_CLEAR_INIT_GROOVY_D=true` in the Dockerfile).

**Fix:** put custom startup scripts in `init-scripts\` and run `docker compose up -d --build`.

### Setting PRE_CLEAR_INIT_GROOVY_D=false did not turn it off
**Cause:** the Jenkins image clears the folder whenever the variable has any value at all, including `false`.

**Fix:** delete the `ENV PRE_CLEAR_INIT_GROOVY_D=true` line from the Dockerfile and rebuild.

### Some startup work didn't happen (for example no Templates folder), and the log shows a script error
**Cause:** Jenkins runs the scripts in `init.groovy.d` one after another as a single step. If one script throws an error, Jenkins logs `GroovyInitScript.init failed ...` and **skips all the scripts after it**. For example, an error in `31-ssh-agent.groovy` means `40-job-templates.groovy` never runs.

**Fix:** find the first error after the `Executing ...init.groovy.d/...` line:
```cmd
docker compose logs | findstr /c:"Executing" /c:"init failed" /c:"Exception"
```
Fix that script (or the `.env` values it reads), then rebuild and restart with `docker compose up -d --build`. Scripts that create things only when they're missing will catch up on that start.

A script you write yourself in `init-scripts\` must also avoid declaring methods (`def name(...) { }`). Groovy names the script's classes after the file, and a file name like `31-my-script.groovy` produces an invalid Java class name for a method's helper class (`ClassFormatError: Illegal class name`). Use a closure instead: `def name = { args -> ... }`.

### I removed a startup script, but what it created is still there
**Cause:** removing a script only stops it from running. Users, nodes, credentials and jobs it already created stay in `jenkins_home`.

**Fix:** delete them in the Jenkins UI (Manage Jenkins -> Nodes / Credentials / Users).

---

## Admin login

### I don't know the admin password
**Cause:** without `JENKINS_ADMIN_PASSWORD` in `.env`, the first start generates a random password.

**Fix:**
```cmd
type C:\MNT\docker\jenkins\jenkins_home\secrets\sloppy-initial-admin-password
```
The user is `admin`, unless `JENKINS_ADMIN_ID` was set.

### I changed the password in .env, but the old one still works
**Cause:** the admin account is only created on a fresh `jenkins_home`. After that it belongs to Jenkins, and restarts never reset it.

**Fix:** change the password in Jenkins (your user -> Security).

### A password with $, #, quotes or spaces doesn't work
**Cause:** older setups let Docker Compose interpret `$` and `#` in `.env`, which silently changes the value.

**Fix:** `compose.yaml` reads `.env` with `format: raw`, so values are taken literally. Write the value with **no quotes** and no trailing spaces, for example `JENKINS_ADMIN_PASSWORD=My$ecret#1`. If the account was already created with a mangled password, reset it in Jenkins or start from a fresh home.

### Log shows "WARNING: user 'admin' exists but does NOT have Overall/Administer"
**Cause:** the admin account exists, but its permission was removed or never granted. The startup script deliberately doesn't repair this.

**Fix:** sign in as a user who still has Administer and grant it in Manage Jenkins -> Security. If nobody can, see the Jenkins documentation on disabling security for recovery.

### Log shows "admin 'xyz' not found, but N other user(s) exist"
**Cause:** `JENKINS_ADMIN_ID` was changed after the first start. Admins are never created or replaced automatically.

**Fix:** create that user in Manage Jenkins -> Users, or set `JENKINS_ADMIN_ID` back.

---

## Credentials from .env

### A credential I defined in .env was not created
**Cause:** `init-scripts\20-username-credentials.groovy` skips a set when:
- **a part is missing:** `ID`, `USER` and `PASSWORD` are all required (`DESCRIPTION` is optional);
- **the ID has other characters:** only letters, digits, `_`, `.` and `-` are allowed. A common slip is copying a GitLab deploy token's user name (`gitlab+deploy-token-...`) into the ID: the `+` belongs in `USER`, which accepts any characters;
- **the ID already exists:** existing credentials are never overwritten.

**Fix:** check the log. It names the set and the missing variable (never the values):
```cmd
docker compose logs | findstr /c:"credential"
```
Correct `.env` (no quotes; the numbers must match, e.g. `SLOPPY_CRED_2_ID` with `SLOPPY_CRED_2_USER`), then run `docker compose up -d` so the container picks up the new `.env`.

### The credential exists, but logging in with it fails
**Cause:** `USER` and `PASSWORD` are used exactly as written in `.env`, including spaces. A trailing space after the password, or quotes around it, become part of the stored value.

**Fix:** correct the credential in Manage Jenkins -> Credentials (update the password). Fix `.env` too, so a future fresh start creates it correctly.

### I changed a password in .env, but Jenkins still uses the old one
**Cause:** credentials are created once. After that they belong to Jenkins, and the startup script never overwrites them.

**Fix:** update the credential in Manage Jenkins -> Credentials. Alternatively delete it there and restart (`docker compose up -d --force-recreate`) to have it recreated from `.env`.

### Is it safe to keep passwords in .env?
**Cause:** `.env` is plain text on disk (gitignored, so it is never committed). Its values become environment variables of the container, which anyone who can run `docker inspect` can read.

**Fix:** after Jenkins has started once, delete the `PASSWORD` lines (and `JENKINS_ADMIN_PASSWORD`) from `.env` and run `docker compose up -d` so the container is recreated without them. Jenkins keeps the credentials and the admin account encrypted in `jenkins_home`. This produces no warnings: a set whose credential already exists needs nothing else. On a later fresh start, put the password lines back so the credentials can be created again.

---

## Optional SSH build node

### I set the SSH variables in .env, but no SSH node appears
**Cause:** `init-scripts\31-ssh-agent.groovy` does nothing unless `SLOPPY_SSH_AGENT_HOST` is set. It also skips the node, with a WARNING, if `SLOPPY_SSH_AGENT_EXECUTORS` or `SLOPPY_SSH_AGENT_PORT` is not a number. And it never changes a node that already exists with that name.

**Fix:** check `docker compose logs | findstr /c:"SSH"`, correct `.env`, then `docker compose up -d`. To apply new settings to an existing node, edit it in Manage Jenkins -> Nodes, or delete it there and restart.

### The SSH node stays offline
**Causes and fixes:**
- **"uses credential ..., which does not exist yet" in the log:** create the "Username with password" credential with the ID from `SLOPPY_SSH_AGENT_CRED_ID` (default `jenkins_agent_credentials`). Either add it in Manage Jenkins -> Credentials, or add a `SLOPPY_CRED_<n>` set with that ID to `.env`.
- **Host key not trusted yet:** the first connection waits for you. Open Manage Jenkins -> Nodes -> the node -> **Trust SSH Host Key**, then relaunch the agent. This protects the login credential from a machine pretending to be your agent.
- **The SSH machine isn't ready:** it needs an SSH server (on Windows: the OpenSSH Server feature), Java 21+ at `SLOPPY_SSH_AGENT_JAVA`, and an account matching the credential. The node's log in Jenkins shows the exact error.

### Jobs run on the SSH node when I expected the Windows inbound node (or the other way round)
**Cause:** both nodes use the label `windows-label` by default, so a job asking for `windows-label` can run on either.

**Fix:** give the SSH node its own label with `SLOPPY_SSH_AGENT_LABELS` (for a new node) or in the node's configuration, and use that label in the Jenkinsfiles that should run there.

---

## Windows build agent

### The agent is offline after a reboot or Docker restart
**Cause:** the agent is a normal program started by hand. Nothing restarts it.

**Fix:** open Command Prompt in the project folder and run `tools\start-agent.bat`.

### The agent keeps printing "Failed to connect: Handshake error"
**Cause:** Jenkins rejected the agent secret. It's wrong, or `jenkins_home` or the node was recreated, which gives the node a new secret. The agent retries forever rather than exiting.

**Fix:** press Ctrl+C and run:
```cmd
tools\start-agent.bat /resetsecret
```
Then paste the secret from Manage Jenkins -> Nodes -> windows_build_agent. Alternatively, `set JENKINS_USER=admin` first: `/resetsecret` then fetches the new secret itself and asks for your Jenkins API token.

### start-agent.bat with JENKINS_USER set still asks for my API token
**Cause:** no secret is saved yet (first run, `/resetsecret`, or the `secrets` folder was deleted). The script then needs the API token to get the secret from Jenkins. Don't paste the agent secret at the token prompt; the prompt wants your Jenkins **API token**. Older versions of the script asked for the token on every run, even with a saved secret.

**Fix:** enter the API token once. Later runs reuse the saved secret in `C:\Jenkins\secrets\agent-secret.txt` and don't ask again.

### start-agent.bat says "agent.jar is up to date" after I upgraded Jenkins
**Cause:** it shouldn't: the script asks Jenkins whether its `agent.jar` is newer than the local file (curl `-z`) and downloads it when it is. If the local file's date was changed by hand, that comparison can be fooled.

**Fix:** delete `C:\Jenkins\agent.jar` and rerun `tools\start-agent.bat`; it downloads a fresh copy.

### Builds run in C:\Jenkins even though I set AGENT_ROOT to another folder
**Cause:** builds always run in the node's **Remote root directory** (set in Jenkins) plus `\workspace`. `AGENT_ROOT` only decides where `agent.jar`, the `secrets` folder and the agent's logs go.

**Fix:** keep both the same. Change the Remote root in Manage Jenkins -> Nodes -> windows_build_agent -> Configure (or `JENKINS_WINDOWS_AGENT_WORKDIR` in `.env` before the node is first created).

### I changed the Remote root, but builds still use the old folder
**Cause:** a connected agent keeps the root it had when it connected.

**Fix:** stop the agent (Ctrl+C) and run `tools\start-agent.bat` again.

### "ERROR: other accounts have permissions on C:\Jenkins\secrets"
**Cause:** the `secrets` folder (or the secret file) has permissions for an account other than yours. The script refuses to store or use a secret there, and deletes any existing one.

**Fix:** delete the folder and rerun. The script recreates it locked to your account:
```cmd
rmdir /s /q C:\Jenkins\secrets
tools\start-agent.bat
```

### "the agent secret can only be pasted in an interactive Command Prompt window"
**Cause:** the secret prompt hides what you type, which only works in a real Command Prompt window. It refuses when input is piped or redirected.

**Fix:** run `tools\start-agent.bat` in a normal Command Prompt window, or `set JENKINS_USER=admin` so the secret is fetched from Jenkins.

### "JENKINS_URL must use https://"
**Cause:** `agent.jar` is downloaded from `JENKINS_URL` and the secret is sent to it. Plain `http://` is only allowed for this machine (`localhost`, `127.0.0.1`).

**Fix:** use `http://localhost:8787/` locally, or an `https://` address (for example your ngrok URL) for a remote Jenkins.

### Jenkins logs a warning about "-jnlpUrl" being deprecated
**Cause:** fetching the agent secret downloads the node's connection file, and Jenkins logs this warning whenever that file is downloaded.

**Fix:** none needed; it's harmless. The agent itself is started with the modern `-url`, `-name` and `-webSocket` options.

---

## Helper scripts in tools\

### "Python 3.10 or newer is required"
**Cause:** the helpers run `tools\src\sloppy_tool.py`, and no usable Python was found. Typing `python` on a fresh Windows install can open the Microsoft Store instead (a stub, not real Python).

**Fix:**
```cmd
winget install Python.Python.3.12
```
Then open a new Command Prompt window. The helpers prefer the `py` launcher.

### A repository URL containing % is changed (for example My%20Project becomes Mygeneric0Project)
**Cause:** an older version of the Python helper wrappers started Python with `call`, which made Command Prompt expand `%` signs a second time. `%2` was read as "the second argument".

**Fix:** update Sloppy Jenkins. The wrappers now resolve the real `python.exe` and invoke it without `call`, so percent-encoded URLs are preserved. If this still happens, check that your local batch files are current.

### A helper hangs at "API token ... (input is hidden)" in a scheduled task or script
**Cause:** an older Python helper trusted `isatty()`, which reports `NUL` as a terminal on Windows even though it is not an interactive console.

**Fix:** update Sloppy Jenkins. The helper now asks Windows whether stdin is attached to a real console and exits clearly instead of waiting on redirected input. For scheduled or CI runs, set `JENKINS_API_TOKEN` and `GITLAB_TOKEN` so no prompt is needed.

### "invalid XML: reference to invalid character number"
**Cause:** the job XML is malformed, contains a raw illegal control character, or was processed by an older Python helper. Jenkins writes XML 1.1 and may use numeric references such as `&#x1b;` for control characters. Python's XML parser normally rejects those XML 1.1-only references.

**Fix:** update Sloppy Jenkins. The helper now safely preserves valid XML 1.1 numeric control-character references while it updates the job. If the error remains, remove the malformed or raw control character from the job (often Configure -> Description), save, and rerun the helper. The operation fails before changing Jenkins or GitLab.

### Line breaks appear in a job's description after running gitlab-webhook.bat
**Cause:** an older Python helper wrote the rare U+2028 (line separator, sometimes pasted from Word or web pages) and U+0085 (next line) characters directly into XML 1.1. XML 1.1 treats them as line endings, so Jenkins normalized them to ordinary line feeds when it loaded the update.

**Fix:** update Sloppy Jenkins. The helper now writes both characters as numeric references, which prevents XML line-ending normalization and preserves the original description. If an older helper already changed the text, correct it once in Configure -> Description.

---

## Job templates

### My changes to Templates/pipeline-from-scm were lost
**Cause:** templates belong to the project (`job-templates\` in the repo) and are refreshed on start whenever they differ.

**Fix:** never edit templates in Jenkins. Copy one (New Item -> Copy from) and edit the copy, or change the XML in `job-templates\` and rebuild.

### The job I copied from a template doesn't build
**Cause:** templates are disabled, and so is a fresh copy.

**Fix:** open the copy, set the repository URL, credential and branch, then click **Enable** and **Save**. `tools\new-job.bat` enables the job for you.

### new-job.bat says "Jenkins rejected the credentials or permissions (HTTP 403)"
**Cause:** reading a template's `config.xml` needs Job/Configure (the optional Extended Read permission isn't installed), and creating a job needs Job/Create.

**Fix:** use an admin, or grant those permissions in Manage Jenkins -> Security.

---

## GitLab webhooks and ngrok

### gitlab-webhook.bat says "ngrok (local API on 127.0.0.1:4040) is not reachable"
**Cause:** the helper needs Jenkins' public address for the webhook, and it gets it from ngrok's local API. ngrok isn't running, or it was started after the helper. GitLab.com can't call `localhost`, so without ngrok (or another public address) there is nothing to point a webhook at.

**Fix:** start ngrok in its own window first (`ngrok http 8787`, or with `--url` for your reserved domain), then rerun the helper. If Jenkins is public some other way, `set NGROK_URL=https://your-public-address` instead. If you don't need GitLab.com to reach Jenkins, you don't need this helper.

### gitlab-webhook.bat says "Jenkins job '...' not found" or "pass the ... path, not a URL"
**Cause:** the helper takes **paths, not URLs**: the job's name in Jenkins and the GitLab project path. Passing `http://localhost:8787/job/myproject` or `https://gitlab.com/me/myproject.git` doesn't work. (Older versions of the helper asked for both tokens first and then reported the URL as a job that doesn't exist.)

**Fix:** pass the job name (`folder/name` for a job in a folder) and the part of the GitLab URL after `https://gitlab.com/`, without `.git`:
```cmd
tools\gitlab-webhook.bat myproject me/myproject
```

### gitlab-webhook.bat says "GitLab did not accept this token (HTTP 401)"
**Cause:** GitLab didn't recognize the token at all. The scopes don't matter yet: a token with too few rights gets HTTP 403 instead. Usual reasons:
- a different token was pasted, for example a deploy token (`gldt-...`), which can only clone or pull;
- the token is expired or revoked (GitLab still lists its scopes);
- the paste picked up extra characters.

Older versions of the helper reported 401 and 403 with the same message.

**Fix:** check the token with hidden input; this prints only its name, scopes, active flag and expiry:
```cmd
py -3 -c "import getpass,json,urllib.request as u;t=getpass.getpass('GitLab token (hidden): ');d=json.load(u.urlopen(u.Request('https://gitlab.com/api/v4/personal_access_tokens/self',headers={'PRIVATE-TOKEN':t})));print({k:d.get(k) for k in ('name','scopes','active','revoked','expires_at')})"
```
If that ends in `HTTP Error 401`, create a new personal access token (avatar -> Edit profile -> Access tokens) with the **api** scope and rerun the helper.

### gitlab-webhook.bat says "GitLab accepted the token but refused access (HTTP 403)"
**Cause:** the token is valid, but it lacks the `api` scope, or your account isn't Maintainer (or Owner) on the project.

**Fix:** use a token with `api`, or ask a project Owner to raise your role.

### The build fails at checkout with "HTTP Basic: Access denied" (GitLab deploy token)
**Cause:** the job's credential holds a GitLab **deploy token** (`gldt-...`) with your own GitLab user name. A deploy token only works with the user name GitLab gave it, such as `gitlab+deploy-token-12345678`. The webhook itself is fine: the build did start.

**Fix:** in GitLab, the project -> Settings -> Repository -> Deploy tokens shows the token's **Username** (it also needs the `read_repository` scope). In Jenkins, Manage Jenkins -> Credentials -> your credential -> Update, set that user name and keep the password. For a future fresh start, use the same user name in `.env` (`SLOPPY_CRED_<n>_USER=gitlab+deploy-token-12345678`; the `+` is fine in a user name, just not in the ID). A deploy token is the right choice here: it can only read the repository. Use your personal access token for `tools\gitlab-webhook.bat`, not for cloning.

### GitLab's webhook test returns 401
**Cause:** the job's GitLab trigger has no secret token, and Jenkins' `/project` endpoint authentication is on (the default), so GitLab must authenticate.

**Fix:** give the job its own secret. Run `tools\gitlab-webhook.bat <job> <group/project>`, or generate one in the job's trigger settings (Advanced -> Secret token -> Generate) and paste it into GitLab's webhook **Secret token** field.

### The webhook stopped working after restarting ngrok
**Cause:** the public ngrok URL changed, so the GitLab webhook points at an old address.

**Fix:** rerun `tools\gitlab-webhook.bat <job> <group/project>`. It updates the same webhook and resends its secret. A reserved ngrok domain avoids this.

### GitLab webhook uses the "signing token" and Jenkins rejects it
**Cause:** the Jenkins GitLab plugin checks GitLab's **Secret token** (`X-Gitlab-Token`), not the newer signing-token option.

**Fix:** put the secret in the webhook's Secret token field.

### "several GitLab hooks match job ..."
**Cause:** more than one webhook in the GitLab project could belong to this job, so the helper won't guess which to change.

**Fix:** delete the extra webhooks in GitLab (Settings -> Webhooks) and rerun the helper. Nothing was changed.

### "GitLab result unknown ... Rerun the helper"
**Cause:** the request to GitLab timed out or the connection dropped, so GitLab may or may not have applied the change. Jenkins was put back to its previous secret.

**Fix:** rerun the helper; it's always safe to repeat.

---

## Other issues

### A few docker compose commands
***Cause*** Working with docker compose
**Fix:** A few commands on building, starting, checking status, executing "java --version" inside the jenkins container, and viewing logs of the jenkins container.

```
docker compose build
docker compose up -d
docker compose ps
docker compose logs --tail 100
docker compose exec jenkins java -version
```

### Setup agent/node manually? 
***Cause*** For quick debugging or testing, you may want to setup the agent/node manually.
**Fix:** Run the commands below, but make sure you have the following prerequisites:

- secret: from Manage Jenkins -> Nodes -> windows_build_agent
- workDir: folder exists (C:\jenkins-agent)
- name: of the agent (try to be unique) (windows_build_agent)

```cmd
curl.exe -sO http://localhost:8787/jnlpJars/agent.jar
java -jar agent.jar -url http://localhost:8787/ -secret [INSERT_SECRET_HERE] -name "windows_build_agent" -webSocket -workDir "C:\jenkins-agent"
```