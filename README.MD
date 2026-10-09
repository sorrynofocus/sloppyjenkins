##  Sloppy Jenkins
### Local Jenkins Docker Container development box

Updated: 2026.10.09

### Purpose: To have a local jenkins instance;  develop shared libraries, debug, and work with the internal Jenkins file system. All of this glory _without_ the need of hitting the production server!

- Run jenkins and learn internals
- Write your own plugins, shared libraries, learn file system, blow it up -- safely, in a container!

## Project stats:
- Linux Debian GNU/Linux 13 (trixie)
- OpenJDK Runtime Environment 21.0.11 - [openjdk.org/projects/jdk/21](https://openjdk.org/projects/jdk/21/)
- Jenkins 2.580.1 LTS - [hub.docker.com/r/jenkins/jenkins](https://hub.docker.com/r/jenkins/jenkins)

## Prerequisites

**_NOTE:_** These instructions assume a **Windows** host. If you're on **Linux** or **macOS**, adjust accordingly: Docker there only runs Linux containers already (there's no container-mode switch, so you can skip step 4: `Docker for Desktop for Windows`). You'll also need to change the paths in `compose.yaml` (example: `C:\MNT\docker\jenkins\jenkins_home`) to a Linux/macOS-style path such as `~/mnt/docker/jenkins/jenkins_home`.

1. You'll need `internet access`.

2. `Command prompt` (or Windows Terminal ).

3. `Python 3.10 or newer` is required for the helpers in `tools\`, including starting the build agent (`tools\start-agent.bat`), creating a job from a template, and the GitLab webhook extra credit. The batch files use the Windows `py` launcher when available and otherwise try `python`.

        winget install Python.Python.3.12

4. `Docker for Desktop for Windows`. This project was constructed as a linux image/container. Docker Desktop install is easy to install.

        Once Docker is setup, we will need to switch to Linux containers to use this project.
        You can do this via right clicking on the white docker whale icon and choose
        "Switch to Linux containers".

        OR

        At the command prompt, and enter:
        "c:\Program Files\Docker\Docker\dockercli" -SwitchLinuxEngine

        Note: You can later switch back to Windows containers via UI or
        "c:\Program Files\Docker\Docker\dockercli" -SwitchWindowsEngine

5. `Java 21 or newer` on the Windows host, for the build agent (Jenkins' `agent.jar`). Get it from the [Adoptium Temurin release page](https://adoptium.net/temurin/releases?version=21&os=windows&arch=x64&mode=filter).

**Optional:** `ngrok` is recommended when Jenkins must be reached from outside your local machine for example, by GitLab, GitHub, another webhook provider, or a remote tester. Jenkins runs locally without it. To install: `winget install ngrok -s msstore`

## Build instructions

> **In a hurry?** Jump to [TL;DR: quick start](#tldr-quick-start). Full setup details? See [Setup, in detail](#setup-in-detail).

The project's source will do *everything* for you. At least, *try to*. Sloppy Jenkins appears to have a lot of files to work with. This is not true. Just setting up a docker image and an environment file is all you need to get started. The rest of the files are helpers, templates, documentation, and a part of the automation.

The project will:

- Build the docker image
- Configure jenkins
- Install recommended plugins (see [plugins/plugins.txt](plugins/plugins.txt) and [plugins/README.txt](plugins/README.txt))
- Set up an admin account on first start (see [init-scripts/](init-scripts/) and [init-scripts/README.txt](init-scripts/README.txt))
- Define a Windows build agent node, `windows_build_agent`
- Provide disabled Pipeline job templates you can copy for your own projects
- Get you started with a Docker container with a local Jenkins instance. This is enough to get a local server up and running with **persistent** server data!


## TL;DR: quick start

**Docker Desktop (Linux containers)**, **Java 21+**, and **Python 3.10+** installed? Right on! Let's GO!

Open a Command Prompt in this project's folder and go. Each step links to [Setup, in detail](#setup-in-detail) below.

1. **Settings.**

    Set at least `JENKINS_ADMIN_PASSWORD` (no quotes). Everything else is optional ([details](#build-the-initial-docker-image)).

    ```cmd
    copy .env.example .env
    notepad .env
    ```

2. **Build and start Jenkins.**

   ```cmd
   docker compose up -d --build
   docker compose logs -f
   ```

   Wait for `Jenkins is fully up and running`, then press `Ctrl+C`. That only stops the log; Jenkins keeps running.

3. **Check the startup.**

    You should witness several logs reporting something similar to `Created`/`exists`/`up to date`. None _should_ say `WARNING`.

   ```cmd
   docker compose logs | findstr /l /c:"[sloppy]"
   ```

4. **Ride your server**

    Login to http://localhost:8787/ as `admin` (or your `JENKINS_ADMIN_ID` from `.env`) with the password from `JENKINS_ADMIN_PASSWORD` you've set.

5. **Create an API token**

    Create it in Jenkins. You'll need this to get an agent/node running in Jenkins. Migrate to your Account profile (top right of Jenkins UI) -> **Security** -> **API Token** -> **Add new Token**. Copy it. You'll definitely need it. Do not lose or commit it!

6. **Connect the build agent**

    Leave Jenkins UI open in the browser.

    Open a separate Command Prompt and head over to the Sloppy Jenkins project's folder (this project's source). Once we connect the agent/node, this window must remain open while the agent is running. If you close it, the agent stops and Jenkins reports the node as offline.

   ```cmd
   set JENKINS_USER=admin
   tools\start-agent.bat
   ```

    The first run asks for the API token (hidden input) that you just copied ([details](#connect-the-build-agentnode)).

    Once the node is connected, you are done. Jenkins will be at http://localhost:8787/ and `windows_build_agent` online. Make jobs from the `Templates` folder ([Job templates](#job-templates)).

    **Done!**

**Running the Jenkins instance at a later time**

Again, open a Command Prompt and head over to the Sloppy Jenkins project's folder (this project's source).

```cmd
docker compose up -d
tools\start-agent.bat
```

> If the secret has been saved from first run, the agent starts without asking for the API token. Otherwise, it fetches it from Jenkins (asks for your API token) or asks you to paste it. You can always reset the secret with `/resetsecret` if the node has been recreated.

**Stop for the day:** `Ctrl+C` in the agent window, then `docker compose stop`.



**If you want to start completely fresh (whY?)** (deletes all Jenkins data: jobs, credentials, users):

```cmd
docker compose down
rmdir /s /q C:\MNT\docker\jenkins\jenkins_home
docker compose up -d --build
```

Then repeat steps `3` through `5` and connect the agent. The node has a new secret, so use `/resetsecret`:

```cmd
set JENKINS_USER=admin
tools\start-agent.bat /resetsecret
```

**Optional, public URL:** `ngrok http 8787 --url https://YOUR_DOMAIN`, and put that address in `.env` as `SLOPPY_JENKINS_URL` ([details](#expose-jenkins-to-the-interwebs)).


## Setup, in detail

The full walkthrough of the steps above, plus ngrok, revisiting the persisted Jenkins instance, connecitng an  agent/node (jnlp), templates, and troubleshooting.

### Build the initial Docker image
1. Once you've switched to Linux containers and downloaded this project's source files, enter the projects' directory and drop to a command prompt.

        For example: If you copied the project's source to C:\docker-dynamic-jenkins-work,
        switch to this directory by typing:

        cd C:\docker-dynamic-jenkins-work

2. Optional: choose the admin account. Copy `.env.example` to `.env` and set `JENKINS_ADMIN_ID` and `JENKINS_ADMIN_PASSWORD`. `.env` is gitignored; never commit it.

        copy .env.example .env
        notepad .env

    Skip this, and Jenkins _creates_ the admin `admin` with a random password (see step 5). Be a real hero, set you own password!

    Optional: in the same `.env`, define **username/password credentials** Jenkins should create on start, for example a Git repository token used by your jobs. The _username/password_ are typical credential in the Credentials Manager in Jenkins.

    Use one numbered set per credential:

        SLOPPY_CRED_1_ID=gitlab-repo-token
        SLOPPY_CRED_1_USER=your-gitlab-user
        SLOPPY_CRED_1_PASSWORD=your-token
        SLOPPY_CRED_1_DESCRIPTION=GitLab repository token

    A credential is created _only_ if its credential ID doesn't exist yet; existing credentials are never overwritten (you can mod them in Manage Jenkins -> Credentials). Values are taken literally: no quotes! `.env` is plain text on disk and its values are visible to anyone who can run `docker inspect`, so once Jenkins has started _you can delete the password lines_. Jenkins keeps the credentials encrypted in the Credential Manager.

      > Note: See `.env.example` and [init-scripts/README.txt](init-scripts/README.txt).

3. To build a docker image, type:

    `docker compose build`

    Get coffee, or tea. Build time: ~10-15 minutes if never built, 3-5 minutes if previous build exist. Jenkins docker image will be completed shortly.

4. Once **success** build is complete, type:

     `docker compose up -d`

    You'll witness feed back, something similar to this:

    > Network docker-dynamic-jenkins-work_default  Created
    > Container local_dev_jenkins  Started

    This means a container has started. You can validate this by typing `docker ps` and validating `local_dev_jenkins` is running.

    <BR>

    If NOT success, then examine the README files in the subfolders to help troubleshoot. Typical issue appear in the plugin folders. There's good documentation to debug the container.

    > Note: Also, it may take some time to bring up the Jenkins server.

    It may appear the server is not running. Wait until you see the familiar message:

    ```
    Please wait while Jenkins is getting ready to work ...
    Your browser will reload automatically when Jenkins is ready.
    ```

    You can inspect the logs of the container to see the progress. Here's a few commands for logging:

    _Show the last 100 lines of the Jenkins container logs:_
    `docker logs -n 100 local_dev_jenkins`

5. In your fav browser migrate to: http://localhost:8787/  (please be patient. Jenkins is starting...)
<BR>

    > On the **first start** with an empty `jenkins_home`, Jenkins creates the admin account with full administrator rights:
    > - with: the `.env` via the `JENKINS_ADMIN_ID` / `JENKINS_ADMIN_PASSWORD` variable values you chose;
    > - without: the `.env`, then `admin` account will have a random password. You can read with the following command:
    >
    >       type C:\MNT\docker\jenkins\jenkins_home\secrets\sloppy-initial-admin-password
    >
    > After that, the account belongs to Jenkins: change the password in Jenkins (your Account Profile -> Security). Jenkins _Restarts_ never reset it and changing `.env` later doesn't change an existing account.


    Jenkins is ready!

    > NOTE: `docker compose` reads `compose.yaml` from the source of this project. There's no alias to set up and nothing to lose by closing your command prompt (unlike before). Any time you need to start, stop, or rebuild Jenkins, just `cd` back into this directory and run the relevant `docker compose` command again.


### Expose Jenkins to the Interwebs

_Optional, but recommended!_

Jenkins is available locally at `http://localhost:8787/`. That's enough for local work. If an external service needs to reach Jenkins - for example, to deliver a webhook - `ngrok` can provide a public HTTPS address that _forwards_ to the local port.

`ngrok` is separate from Jenkins and runs on the host system. It is not installed in the Jenkins image. Install it only if you need external access. On Windows, the installation is quick and simple (about 10-15 minutes and most of that time is just creatign an account):

```cmd
winget install ngrok -s msstore
```

Create an ngrok account, obtain its authtoken, and configure the local ngrok agent:

```cmd
ngrok config add-authtoken "YOUR_NGROK_AUTHTOKEN"
```

Start a tunnel to Jenkins:

```cmd
ngrok http 8787
```

_That's it!_

If your account has an assigned development domain, specify it to reuse the same public URL:

```cmd
ngrok http 8787 --url https://YOUR_ASSIGNED_DOMAIN
```

```text
External service -> public ngrok HTTPS address -> localhost:8787 -> Jenkins container
```

Without `--url`, ngrok assigns a random public URL that may change every time you start it. The public URL is shown in the ngrok console output. To keep the same URL between starts, use the assigned development domain with `--url` as shown above.

GitLab, GitHub, and other services are responsible for their own webhook or integration configuration. Jenkins plugins may provide provider-specific endpoints and authentication options.

Optional extra credit: [docs/extra-credit-gitlab-webhooks.md](docs/extra-credit-gitlab-webhooks.md) shows one way to connect a GitLab project to a Jenkins job through ngrok, including a helper that sets up the webhook.

Before exposing Jenkins, _make sure the admin password is strong and that authentication is enabled_! _**Never commit**_ the ngrok authtoken, Jenkins API tokens, SCM credentials, or webhook secrets.

`Ctrl+C` will stop the ngrok tunnel when external access is no longer needed. and, again, this is optional.


### Revisiting the Jenkins instance

Once the image has been built, you can run the container at any time to ready the Jenkins instance. If you followed the instructions above, Jenkins will be setup and ready to run. If you closed down the container, or perhaps rebooted the Jenkins instance, you can easily run the instance again because you have a working image to run a new container.
_Because the data is persistent_, your Jenkins instance will retain the previous configuration, logs, changes to plugins, etc.

To revisit your Jenkins instance at a later time, you do so by these easy instructions. In fact, you'll notice that the instructions are the same as the initial build instructions, except you don't need to build the image again.

1. Open a command prompt.

2. Move to this project's directory (source to Sloppy Jenkins)

3. Type

    `docker compose up -d`

    <BR>

    If your Jenkins container is already running, this is a no-op; compose only (re)creates the container when the image or config has _actually changed_.

    You'll witness feed back, something similar to this:

    `Container local_dev_jenkins  Started`

    This means _a container has started_! You can validate this by typing `docker ps` and validating `local_dev_jenkins` is running.

    If NOT success, then examine the logs and `README` files in the plugin subfolders to help troubleshoot.

    The docker logs can also provide useful info ofr troubleshooting. Here's a few commands for logging:

    _Show the last 100 lines of the Jenkins container logs:_

    `docker compose logs --tail 100`

    _Show the live logs of the Jenkins container:_

    `docker compose logs -f`

4. In your browser migrate to: http://localhost:8787/  (again.... please be patient. Jenkins is a booting!)

    NOTE: log in with the admin account created on the first start (see [Build the initial Docker image](#build-the-initial-docker-image), step 5).

5. Jenkins is ready when you see the login screen!


### Connect the build agent/node

The Jenkins controller deliberately has **zero** executors. Builds run on agents/nodes so the controller can remain focused on coordinating work. On the first start, Jenkins creates an exclusive inbound Windows node named `windows_build_agent` with one executor, the label `windows-label`, and remote root `C:\Jenkins` (mod these in `.env`, see `.env.example`). An existing node is never changed by a restart.

An inbound agent does not require an SSH server, a fixed host IP, or a username/password credential. It requires network access to Jenkins and Java 21 or newer on the Windows host.

_Note: you can get a newer Java from the [Adoptium Temurin release page](https://adoptium.net/temurin/releases?version=21&os=windows&arch=x64&mode=filter)_

Connect the Windows host as the agent from a Command Prompt in this project directory:

```cmd
tools\start-agent.bat
```

What it does on each run:
1. Checks Python and Java 21+, and creates `C:\Jenkins` if needed.
2. Gets `agent.jar` from Jenkins only when it's missing or Jenkins has a newer one (for example after a Jenkins upgrade). Otherwise it prints `agent.jar is up to date.`
3. Uses the saved agent secret if there is one (`Using the saved agent secret...`). Otherwise it fetches the secret from Jenkins (when `JENKINS_USER` is set) or asks you to paste it. See [The agent secret](#the-agent-secret) below.
4. Starts the agent over WebSocket (no port 50000 needed). Leave the window open while you build; `Ctrl+C` stops the agent.

> Note: `tools\start-agent.bat` is optional. To start the agent yourself, you can run it from a terminal. Here comes an example to call the agent from the terminal (follow instructions below to obtain an agent/node secret):
>```
>curl.exe -sO http://localhost:8787/jnlpJars/agent.jar
>java -jar agent.jar -url http://localhost:8787/ -secret [AGENT_SECRET_HERE] -name "windows_build_agent" -webSocket -workDir "C:\Jenkins"
>```
>This manual command puts the secret **on the command line**, where it can show up in the process list and your command history. `tools\start-agent.bat` avoids that by passing it from a locked file (`-secret @file`).

Python runs the readable helper in `tools\src\sloppy_tool.py`; Java 21 is still required by Jenkins' own `agent.jar`. Run the script yourself whenever you want the agent online, the same way you start ngrok.

### The agent secret

Jenkins generates a secret for each node; the agent needs it to log in. You can see it at **Manage Jenkins -> Nodes -> windows_build_agent**: it's the long value after `-secret` in the command Jenkins shows.

- **First run:** the script needs the secret once. Either paste it when asked (input is hidden), or let the script fetch it: `set JENKINS_USER=admin` first, and enter your Jenkins **API token** when asked (Jenkins -> your user -> Security -> API Token). That prompt wants the API token, not the agent secret.
- **Later runs:** no prompt. The script reuses the secret saved in `C:\Jenkins\secrets\agent-secret.txt`, whether `JENKINS_USER` is set or not.
- **After recreating `jenkins_home` or the node:** the node gets a new secret, and the agent reports `Failed to connect: Handshake error`. Press `Ctrl+C` and run `tools\start-agent.bat /resetsecret`, which deletes the saved secret and pastes or fetches the new one.

| Command | What happens |
|---|---|
| `tools\start-agent.bat` | Uses the saved secret; asks you to paste it if none is saved. |
| `set JENKINS_USER=admin` then `tools\start-agent.bat` | Uses the saved secret; fetches it from Jenkins (asks for your API token) if none is saved. |
| `tools\start-agent.bat /resetsecret` | Forgets the saved secret, then pastes or fetches a new one as above. |

Safety:
- The `secrets` sub-folder is locked to your Windows account before the secret is written. If any other account has permissions on the folder or file, the script deletes the secret and stops (delete the `secrets` folder and rerun; it recreates it locked).
- Pasting _only works in an interactive Command Prompt window_, where the input is hidden.
- `JENKINS_URL` must be `https://` unless it points at this machine (`localhost`), because `agent.jar` is downloaded from it and the secret is sent to it.
- With the script, the secret never goes on a command line (unlike the manual command above). And **never** commit it!
- When the script fetches the secret, Jenkins may log a warning about the `-jnlpUrl` option being deprecated. _That_ warning is caused by downloading the agent's connection file and is harmless: the agent is started with the modern `-url`, `-name` and `-webSocket` options.

**Read the secret yourself through the API** (this is what the script does with `JENKINS_USER`):

```cmd
curl -u admin http://localhost:8787/computer/windows_build_agent/jenkins-agent.jnlp
```

curl asks for the password with hidden input: type your **API token** there. Don't write `-u admin:TOKEN`, because that puts the token in your command history. The secret is the first `<argument>...</argument>` in the reply.

Other `tools\start-agent.bat` settings (`set` them before running it):
- `JENKINS_URL` (default `http://localhost:8787/`)
- `AGENT_NAME` (default `windows_build_agent`)
- `AGENT_ROOT` (default for this project: `C:\Jenkins`). Keep `AGENT_ROOT` the same as the node's **Remote root directory** in Jenkins. Builds always run in `<Remote root>\workspace`; `AGENT_ROOT` only decides where `agent.jar`, the `secrets` folder and the agent's logs live. A changed Remote root takes effect the next time the agent connects.

Install any build tools your projects need (Visual Studio, GNU Make, ...) for the Windows account that runs the agent.

Node definitions persist under `C:\MNT\docker\jenkins\jenkins_home\nodes\<node-name>\config.xml`. Jenkins should own that file. Change nodes in the Jenkins UI rather than editing the XML.

**Optional: an SSH-launched node.** If another machine runs an SSH server, Jenkins can start the agent on it over SSH instead of you running `start-agent.bat` there. Set `SLOPPY_SSH_AGENT_HOST` (and optionally the other `SLOPPY_SSH_AGENT_*` values) in `.env`, plus a `SLOPPY_CRED_<n>` set for its login (see `.env.example`). Then run `docker compose up -d`. The node is then created once. The first connection waits until you trust its host key in **Manage Jenkins -> Nodes**. It uses the label `windows-label` by default, the same as the inbound node; set `SLOPPY_SSH_AGENT_LABELS` to keep their jobs apart.


### Job templates

Jenkins starts with a `Templates` folder of _disabled_ Pipeline jobs. They never build,  they're starting points you copy and mod for your own projects. The templates are:

- `Templates/pipeline-from-scm`: Pipeline from SCM. Works with any Git server.
- `Templates/gitlab-pipeline-from-scm`: the same plus a GitLab push/merge-request trigger (_extra bonus credit_, see [docs/extra-credit-gitlab-webhooks.md](docs/extra-credit-gitlab-webhooks.md)).

To make your own job:

1. **New Item**, type a name, and in **Copy from** enter `Templates/pipeline-from-scm`. Click **OK**.
2. Set **Repository URL**, pick your **Credentials** (add one under Manage Jenkins -> Credentials if needed) and the **Branch**.
3. Click **Enable** and **Save**.

Your project's `Jenkinsfile` chooses the agent, for example `agent { label 'windows-label' }`.

Or create it from Command Prompt with the same result:

```cmd
set JENKINS_USER=admin
tools\new-job.bat myproject generic "https://gitlab.com/me/myproject.git" main my-repo-credential
```

The Python helper asks for your Jenkins API token with hidden input (or uses `JENKINS_API_TOKEN` if you set it). Your user needs Job/Create on the destination and Job/Configure on the template (reading a job's `config.xml` requires `Configure`, because the optional `Extended Read permission` isn't installed). An admin has all of these.

Templates come from [job-templates/](job-templates/) in this project and are refreshed on every start, so don't edit them in Jenkins; edit your copies. Your copies are independent and are never changed by template updates.


### Troubleshooting

Something not working? [docs/troubleshooting.md](docs/troubleshooting.md) is a collection of compiled experiences uncovered (slow first start, admin password, agent secret and handshake errors, helper scripts, templates, webhooks), each with its cause and fix.


### Manual step: enabling Content-Security-Policy enforcement

Manage Jenkins will show an admin warning recommending CSP enforcement be turned on (`jenkins.security.csp.impl.CspRecommendation`). This is a core Jenkins feature (since 2.539) with three ways to turn it on: the "Enforce Content Security Policy" checkbox under Manage Jenkins -> Security, Configuration-as-Code (`security: contentSecurityPolicy: enforce: true`, which would need the `configuration-as-code` plugin added), or the system property `jenkins.security.csp.CspHeader.headerName`.

This is left as a manual, one-time step rather than baked into an init script: the system-property route is the only one that's scriptable from `init-scripts/`, but setting it also permanently removes the UI checkbox afterward (admins can no longer toggle it from **Manage Jenkins -> Security** once set that way), which didn't seem worth trading away for a "sloppy"/local dev box. Since `jenkins_home` is a persistent volume, checking the box once via the UI survives container restarts/rebuilds just fine - no need to redo it each time.

_Note:_  don't confuse this with the older, narrower `hudson.model.DirectoryBrowserSupport.CSP` system property (settable via Groovy/`System.setProperty`) - _that_ one only controls the CSP header for statically-served content (archived artifacts, workspace browser, HTML Publisher reports, etc.) and won't clear this particular admin warning.


### For the curious

```text
sloppyjenkins/
├── compose.yaml                  Docker Compose: ports 8787/50000, jenkins_home mount, optional .env
├── Dockerfile                    Jenkins LTS image + plugins + startup scripts + job templates
├── .env.example                  Every optional setting; copy to .env (gitignored, never commit it)
├── .gitignore
├── README.MD                     You are here
├── docs/
│   ├── troubleshooting.md        Symptom -> cause -> fix for everything we tripped over
│   └── extra-credit-gitlab-webhooks.md   GitLab -> ngrok -> Jenkins webhook walkthrough
├── init-scripts/                 Copied into init.groovy.d; run on EVERY Jenkins start, in name order
│   ├── 00-controller.groovy      0 controller executors, CSRF, skip setup wizard, Jenkins URL
│   ├── 10-security.groovy        Admin account on a fresh jenkins_home
│   ├── 20-username-credentials.groovy   SLOPPY_CRED_<n>_* sets from .env -> Jenkins credentials
│   ├── 30-windows-agent.groovy   Inbound node windows_build_agent (create if missing)
│   ├── 31-ssh-agent.groovy       Optional SSH node (only when SLOPPY_SSH_AGENT_HOST is set)
│   ├── 40-job-templates.groovy   Templates folder, refreshed from job-templates/
│   └── README.txt
├── job-templates/                Disabled Pipeline jobs to copy (Templates/<name> in Jenkins)
│   ├── pipeline-from-scm.xml
│   └── gitlab-pipeline-from-scm.xml
├── plugins/
│   ├── plugins.txt               Plugins installed into the image
│   ├── capture-installed-plugins.bat   Writes the running Jenkins' plugins to plugins-installed-snapshot.txt
│   ├── capture-installed-plugins.ps1   (does the work for the .bat)
│   └── README.txt
└── tools/                        Windows helpers (Command Prompt + Python 3.10+, standard library only)
    ├── start-agent.bat           Connect this PC as the build agent
    ├── new-job.bat               Create a job from a template
    ├── gitlab-webhook.bat        Per-job webhook secret + GitLab webhook (extra credit)
    └── src/
        ├── find-python.bat       Finds a usable Python for the .bat files
        └── sloppy_tool.py        The helper behind all three (run "selftest" to check it)
```

Outside the project, on your PC:

```text
C:\MNT\docker\jenkins\jenkins_home\   All Jenkins data (jobs, users, credentials, plugins). Delete it to start fresh.
C:\Jenkins\                           The build agent: agent.jar, secrets\ (locked to you), workspace\ (builds)
```

- While Jenkins is running:
    - All data is persisted in the location `C:\MNT\docker\jenkins\jenkins_home`
    - If you need to restart Jenkins, type `docker compose up -d` at a command prompt in this project directory. If you've edited the `Dockerfile` or `plugins/plugins.txt`, use `docker compose up -d --build` instead so the image gets rebuilt first.

- Startup scripts belong to this project: on every start, Jenkins' `init.groovy.d` folder is replaced by the scripts in [init-scripts/](init-scripts/). Don't drop scripts into `C:\MNT\docker\jenkins\jenkins_home\init.groovy.d` by hand (they are deleted on the next start).  Add them to `init-scripts/` and run `docker compose up -d --build`. See [init-scripts/README.txt](init-scripts/README.txt).

- If need access to the Jenkins container (to poke around the OS, jenkins file systems, etc.), type:

    ```
    docker compose exec jenkins /bin/bash
    ```


- To _end_ your Jenkins container experience, type:

    ```
    docker compose down
    ```



###  Recording your modded Jenkins changes back into the source

Jenkins keeps everything you change in the UI (new plugins, jobs, nodes, settings) in `C:\MNT\docker\jenkins\jenkins_home`, **not** in this project. That's fine day to day, but a fresh start (or another PC cloning this repo) only gets what the source describes. If you want your modifications to survive a fresh start, record it in the source:

| You changed in Jenkins... | Record it in... |
|---|---|
| Installed or updated plugins | `plugins/plugins.txt` (see below) |
| A job you want to reuse as a starting point | `job-templates/<name>.xml` |
| Credentials | your own `.env` as a `SLOPPY_CRED_<n>_*` set (never in the repo) |
| The inbound or SSH node's settings | `.env` (`JENKINS_WINDOWS_AGENT_*`, `SLOPPY_SSH_AGENT_*`), see `.env.example` |
| Other settings (Manage Jenkins -> System, Security, ...) | a new startup script in `init-scripts/` |
| The Jenkins version | the `FROM jenkins/jenkins:...` line in `Dockerfile` |

**Plugins.** Snapshot what the running Jenkins has, then list the plugins that aren't in `plugins.txt` yet. In Command Prompt, from this project's folder (the snapshot tool accepts your API token as the password):

```cmd
set JENKINS_ADMIN_USERNAME=admin
set JENKINS_ADMIN_PASSWORD=YOUR_API_TOKEN
plugins\capture-installed-plugins.bat
for /f "tokens=1 delims=:" %p in (plugins\plugins-installed-snapshot.txt) do @findstr /i /r /c:"^%p$" /c:"^%p:" plugins\plugins.txt >nul || echo %p
```

The last command prints each plugin name that's installed but missing from `plugins.txt` (some are just dependencies of the ones you added; listing them is harmless). Add the names you want to `plugins/plugins.txt`, one per line, and keep the style the file uses (unpinned unless you need a specific version, see [plugins/README.txt](plugins/README.txt)). Then `docker compose up -d --build`. Close the Command Prompt window afterwards so the token isn't left in it.

**Jobs.** A job lives in `jenkins_home\jobs\<name>\config.xml`. To turn one into a template, copy that file to `job-templates\<name>.xml`, set `<disabled>true</disabled>`, and remove anything personal or secret first: values that look like `{AQAAABAAAA...}` are encrypted with *this* Jenkins' key and are useless anywhere else (for example a GitLab `secretToken`; rerun `tools\gitlab-webhook.bat` instead). Rebuild, and it shows up as `Templates/<name>`. Better still, keep the build logic in the project's own `Jenkinsfile`, so the job itself stays a thin "Pipeline from SCM" copy of a template.

**Settings.** Write a small Groovy script in `init-scripts/` (for example `50-my-settings.groovy`). It runs on **every** start, so make it check before it changes anything, like `00-controller.groovy` does. Try the code in **Manage Jenkins -> Script Console** first. Use closures instead of named methods (see [docs/troubleshooting.md](docs/troubleshooting.md)), and remember that one failing script stops all later ones.

**Never copy** `jenkins_home\secrets\`, `credentials.xml`, `users\` or `master.key` into the project. They hold keys and passwords.

**Validation:** the real validation is a fresh start (see [TL;DR: quick start](#tldr-quick-start), "start completely fresh"). Back up `jenkins_home` first if you might want it back (that's how this project was built/validated).


