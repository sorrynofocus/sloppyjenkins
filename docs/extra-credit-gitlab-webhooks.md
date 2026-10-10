# Extra credit: GitLab webhooks through ngrok

This is optional. Sloppy Jenkins works without it. It shows one way to let a GitLab.com project start a Jenkins build when you push, using ngrok to reach your local Jenkins.

```text
GitLab.com -> https://<your-ngrok-domain>/project/<job> -> localhost:8787 -> Jenkins container
```

## TL;DR: worked example (powerprof)

For this example, I'm using my own GitLab project. Swap in your own names; the steps are the same. The numbered sections further down explain each piece in more detail.

| What | For this example |
|---|---|
| Jenkins job | `powerprof` |
| GitLab repository | `https://gitlab.com/grp-cw/powerprof-windows-s0-s3-sleep-states-rtc-timers.git` |
| Branch | `main`, with a `Jenkinsfile` at the repository root |
| Jenkins credential | `gitlab-deploy-token-16091230`: Username with password, holding a GitLab **deploy token** |

> **Remember:** the repository credential is the *project's deploy token*, and **ngrok must be running**. GitLab.com can't reach `localhost`: no ngrok, no webhook.

### What you need first

- Jenkins up, and the agent connected (`tools\start-agent.bat`). The project's `Jenkinsfile` picks the agent by label, for example `agent { label 'windows-label' }`.
- ngrok running in its own window: `ngrok http 8787 --url https://<your-reserved-domain>` (or plain `ngrok http 8787`).
- A **Jenkins API token**: your user (top right) -> **Security** -> **API Token** -> **Add new Token**.
- Two **GitLab tokens**. They are *not* interchangeable:

| Token | Starts with | Where to make it | Scope | Used for |
|---|---|---|---|---|
| Deploy token | `gldt-` | the project -> **Settings -> Repository -> Deploy tokens** | `read_repository` | the Jenkins credential that clones the repository |
| Personal access token | `glpat-` | your avatar -> **Edit profile -> Access tokens** | `api` (and Maintainer on the project) | `tools\gitlab-webhook.bat` only |

GitLab shows a token's value only once, right after you create it. Copy it then.

### Step 1: the deploy token and the Jenkins credential

1. **GitLab:** open the project -> **Settings -> Repository**, scroll down, and click **Expand** next to **Deploy tokens**. Add a token: give it a name, leave *Username* empty (GitLab makes one like `gitlab+deploy-token-16091230`), tick `read_repository`, create it, and copy the `gldt-...` value.
2. Under **Active deploy tokens**, the table shows each token's Name, **Username**, Scopes and Expires. Note the **Username**.
3. **Jenkins:** **Manage Jenkins -> Credentials -> System -> Global credentials -> Add Credentials**, kind **Username with password**:
   - **Username:** the deploy token's Username (`gitlab+deploy-token-...`), **not** your GitLab login
   - **Password:** the `gldt-...` token
   - **ID:** `gitlab-deploy-token-16091230`

   Or put it in `.env` as a `SLOPPY_CRED_<n>_*` set, so a fresh start creates it for you (see `.env.example`).

Make sure the user name **and** the token match. With your own GitLab login as the user name, the build fails at checkout with `HTTP Basic: Access denied` (ask me how I know).

### Step 2: create the job

```cmd
set JENKINS_USER=admin
tools\new-job.bat powerprof gitlab "https://gitlab.com/grp-cw/powerprof-windows-s0-s3-sleep-states-rtc-timers.git" main gitlab-deploy-token-16091230
```

| Parameter | Example | Meaning |
|---|---|---|
| job name | `powerprof` | the job's name in Jenkins (`http://localhost:8787/job/powerprof/`) |
| template | `gitlab` | copies `Templates/gitlab-pipeline-from-scm`, which has the GitLab trigger (`generic` copies the plain one) |
| repository URL | `"https://gitlab.com/grp-cw/...-timers.git"` | the repository Jenkins clones; keep the quotes |
| branch | `main` | the branch to build |
| credential ID | `gitlab-deploy-token-16091230` | the Jenkins credential from step 1 |

It asks for your Jenkins API token, copies the template, fills in the repository, branch and credential, and enables the job. (Doing the same by hand with **New Item -> Copy from** works too, but there's no need.) The job's GitLab trigger has **no secret token yet**; that's the next step. Using your own project? See [new-job.bat in detail](#2-create-the-job-new-jobbat-in-detail) for what each parameter means and where to find your values.

### Step 3: connect Jenkins and GitLab

```cmd
set JENKINS_USER=admin
tools\gitlab-webhook.bat powerprof grp-cw/powerprof-windows-s0-s3-sleep-states-rtc-timers
```

| Parameter | Example | Meaning |
|---|---|---|
| job path | `powerprof` | the job name from step 2, **not** `http://localhost:8787/job/powerprof` |
| project path | `grp-cw/powerprof-windows-s0-s3-sleep-states-rtc-timers` | the repository URL without `https://gitlab.com/` and without `.git` |

It prints the webhook URL it will use, asks for your Jenkins API token, and **last** asks for the GitLab `glpat-...` token (a `gldt-...` deploy token gets HTTP 401 here). Then it:

- generates a new **secret token** for this job and saves it in the job (**Configure -> Triggers -> Build when a change is pushed to GitLab -> Advanced -> Secret token**);
- creates, or updates, the GitLab webhook `https://<your-ngrok-domain>/project/powerprof` with the same secret in its **Secret token** field. GitLab sends it in the `X-Gitlab-Token` header, and Jenkins only accepts requests that carry it.

```text
Webhook URL: https://<your-ngrok-domain>/project/powerprof
Jenkins API token for 'admin' (...; input is hidden):
GitLab personal access token ('api' scope, Maintainer on the project; input is hidden):
Job 'powerprof': GitLab hook <id> updated -> https://<your-ngrok-domain>/project/powerprof
```

The first time, the last line says `created` instead of `updated`. **Rerun this step whenever your ngrok URL changes** (a reserved ngrok domain avoids that). For every step it takes, both parameters and where to find your own values, see [gitlab-webhook.bat in detail](#3a-connect-both-sides-gitlab-webhookbat-in-detail).

GitLab shows a warning to use a *signing token* instead of a secret token. The Jenkins GitLab plugin only checks the secret token, so ignore it for now; a future Sloppy Jenkins update may handle signing tokens.

### Step 4: check the job

Open `http://localhost:8787/job/powerprof/configure`:

- the job is enabled;
- **Repository URL**, **Branch** `*/main` and **Credentials** `gitlab-deploy-token-16091230` are set;
- **Triggers -> Build when a change is pushed to GitLab -> Advanced -> Secret token** is filled in (it's shown hidden).

### Step 5: test it

In GitLab: **Settings -> Webhooks**, then on your webhook **Test -> Push events**. GitLab should answer HTTP 200, and a build starts. Watch it at `http://localhost:8787/job/powerprof/lastBuild/console`. When the whole chain works, the log shows:

1. `Started by GitLab push by <your name>`: GitLab -> ngrok -> Jenkins, secret accepted.
2. `Obtained Jenkinsfile from git ...`: read from `main`.
3. `Running on windows_build_agent in C:\Jenkins\workspace\powerprof`.
4. `using credential gitlab-deploy-token-16091230`, then the checkout (for me: revision `1b89b89`).
5. The `Jenkinsfile`'s own stages (for me: *Verify Windows toolchain*, then *Build Powerprof library* with Visual Studio 2022 and `make`, 0 errors).
6. Post actions: artifacts archived and fingerprinted. `Finished: SUCCESS`.

### If it goes wrong

| You see | Fix |
|---|---|
| `ngrok (local API on 127.0.0.1:4040) is not reachable` | start ngrok first, then rerun step 3 |
| `pass the ... path, not a URL` | use the paths from the step 3 table |
| `GitLab did not accept this token (HTTP 401)` | wrong token at the GitLab prompt: use the `glpat-...` token, not the `gldt-...` one, and check that it hasn't expired |
| GitLab's webhook test returns 401 | the secrets don't match: rerun step 3 |
| Build fails at checkout with `HTTP Basic: Access denied` | the credential's user name isn't the deploy token's Username: fix it (step 1) |

More in [troubleshooting.md](troubleshooting.md).

## 1. Prerequisites

- Jenkins running, and ngrok running: `ngrok http 8787` (see the main README). A reserved ngrok domain keeps the URL stable.
- Python 3.10 or newer on the Windows host. The batch helpers use only Python's standard library.
- A Jenkins credential that can read the repository, stored as **Username with password**. For GitLab, a project deploy token with `read_repository` is best (see the TL;DR, step 1); a project or personal access token with `read_repository` works too.

## 2. Create the job: new-job.bat in detail

`tools\new-job.bat` makes a real, working Pipeline job from one of the templates in the `Templates` folder, so you don't click through **New Item -> Copy from** and the configure page yourself. Doing it by hand gives the same result.

```cmd
set JENKINS_USER=admin
tools\new-job.bat <job name> <generic|gitlab> "<repository URL>" [branch] [credential ID]
```

**What it does, in order:**

1. Asks for your Jenkins API token (hidden input).
2. Checks that no job with that name exists yet (an existing job is **never** overwritten), and that the folder exists, if you gave a `folder/name`.
3. Reads the template's configuration (`Templates/gitlab-pipeline-from-scm` or `Templates/pipeline-from-scm`).
4. Fills in the repository URL, the branch and the credential ID, marks the job **enabled**, and sets its description to "Created from <template> by tools\new-job.bat".
5. Creates the job and prints its address, for example `http://localhost:8787/job/powerprof/`.

Everything else comes from the template as is: the Pipeline reads `Jenkinsfile` from the repository root, and the `gitlab` template's trigger reacts to pushes, merge requests and comments, on all branches.

**Parameters, and where to find your own values:**

| # | Parameter | Required? | In the powerprof example | Where to find your value |
|---|---|---|---|---|
| 1 | job name | yes | `powerprof` | Your choice. It becomes the job's name and its address (`/job/powerprof/`) and, later, the job path for `gitlab-webhook.bat`. Use `folder/name` to put it in an existing Jenkins folder. |
| 2 | template | yes | `gitlab` | `gitlab` if GitLab should start builds with a webhook (copies `Templates/gitlab-pipeline-from-scm`); `generic` for any other Git server, with no trigger (copies `Templates/pipeline-from-scm`). |
| 3 | repository URL | yes | `"https://gitlab.com/grp-cw/powerprof-windows-s0-s3-sleep-states-rtc-timers.git"` | GitLab project page -> **Code** -> **Clone with HTTPS**. Keep the quotes. |
| 4 | branch | no, default `main` | `main` | The branch to build; `main` becomes `*/main`. GitLab project -> **Code -> Branches**. |
| 5 | credential ID | no, default `scm-credentials` | `gitlab-deploy-token-16091230` | The **ID** of a Jenkins *Username with password* credential that can read the repository: **Manage Jenkins -> Credentials**, column **ID**. Create it first (TL;DR, step 1). |

**Settings it reads:** `JENKINS_USER` (required, your Jenkins user name), `JENKINS_API_TOKEN` (optional; otherwise asked for with hidden input), and `JENKINS_URL` (default `http://localhost:8787/`). Your Jenkins user needs Job/Create, and Job/Configure on the template. An admin has both.

**What you'll see:**

```text
Jenkins API token for 'admin' (Jenkins -> your user -> Security -> API Token; input is hidden):
Created job 'powerprof' from Templates/gitlab-pipeline-from-scm: http://localhost:8787/job/powerprof/
GitLab trigger has no secret yet: run tools\gitlab-webhook.bat or generate one in the job's trigger settings.
```

If you left out the credential ID, it also reminds you that the job uses `scm-credentials`, which you then create, or swap for another credential in the job.

**The new job is not webhook-ready yet.** Its GitLab trigger has no secret token. While it's empty, and the global "Enable authentication for '/project' end-point" setting is on (the default, under Manage Jenkins -> System -> GitLab), GitLab can only trigger the job with Jenkins user/API-token credentials. Each job should get its own secret token instead, using either of the two options below.

## 3a. Connect both sides: gitlab-webhook.bat in detail

`tools\gitlab-webhook.bat` wires one Jenkins job to one GitLab project, so a push in GitLab starts a build. It sets **both** sides with the same per-job secret, so you never copy a secret between browser tabs.

**This helper needs ngrok.** GitLab.com can't reach `localhost`, so the webhook must point at Jenkins' public ngrok address. Start ngrok first (`ngrok http 8787`, in its own window), or `set NGROK_URL=https://your-domain.ngrok-free.dev` if Jenkins is public some other way. Without public access to Jenkins there's nothing for a GitLab.com webhook to call, and you don't need this helper.

```cmd
set JENKINS_USER=admin
tools\gitlab-webhook.bat <job path> <GitLab project path>
```

**What it does, in order:**

1. Checks that both arguments are paths, not URLs.
2. Finds Jenkins' public address from ngrok's local API (`127.0.0.1:4040`), or uses `NGROK_URL`, and prints the webhook URL it will use: `https://<ngrok-domain>/project/<job path>`.
3. Asks for your Jenkins API token, and checks that the job exists and has a GitLab trigger (made from the `gitlab` template).
4. Only then asks for your GitLab personal access token, and looks up the project's existing webhooks.
5. Generates a new random **secret token** and saves it in the job (**Configure -> Triggers -> Build when a change is pushed to GitLab -> Advanced -> Secret token**).
6. Creates the GitLab webhook, or updates the one it made before, with that URL and the same secret, for push, merge request and comment events. GitLab sends the secret in the `X-Gitlab-Token` header, and Jenkins only accepts requests that carry it.

Steps 1 to 4 change nothing, so a wrong argument, a missing ngrok or a wrong token stops it with nothing changed.

**Parameters, and where to find your own values** (both are **paths, not URLs**):

| # | Parameter | In the powerprof example | Where to find your value | Not this |
|---|---|---|---|---|
| 1 | job path | `powerprof` | The job name you gave `new-job.bat`. It's the part after `/job/` in the job's address; for a job in a folder, `folder/name`. | `http://localhost:8787/job/powerprof/` |
| 2 | GitLab project path | `grp-cw/powerprof-windows-s0-s3-sleep-states-rtc-timers` | The project's address without `https://gitlab.com/` (and without `.git`): the group or user name, a slash, then the project name. | `https://gitlab.com/grp-cw/....git` |

**Tokens it asks for** (both with hidden input, used only for this run, never saved or printed):

| Prompt | Token | Where to get it |
|---|---|---|
| first | your **Jenkins API token** | Jenkins: your user (top right) -> **Security** -> **API Token** -> **Add new Token** |
| last | a GitLab **personal access token** (`glpat-...`) with the **api** scope; your account needs **Maintainer** (or Owner) on the project | GitLab: your avatar -> **Edit profile** -> **Access tokens**. A deploy token (`gldt-...`) gets HTTP 401 here. |

You can set `JENKINS_API_TOKEN` and `GITLAB_TOKEN` first instead of typing them at the prompts, but don't type tokens with `set /p`, because it shows them on screen.

**Settings it reads:** `JENKINS_USER` (required), `JENKINS_URL` (default `http://localhost:8787/`), `GITLAB_URL` (default `https://gitlab.com`; set it for a self-managed GitLab), and `NGROK_URL` (optional, otherwise it asks ngrok). Tokens are only sent over `https://`; plain `http://` is allowed only for `localhost`, so a self-managed GitLab must use HTTPS.

**What you'll see:**

```text
Webhook URL: https://<your-ngrok-domain>/project/powerprof
Jenkins API token for 'admin' (...; input is hidden):
GitLab personal access token ('api' scope, Maintainer on the project; input is hidden):
Job 'powerprof': GitLab hook <id> updated -> https://<your-ngrok-domain>/project/powerprof
```

`created` instead of `updated` the first time.

**Good to know:**

- **Run it again whenever the ngrok URL changes.** It finds its own webhook by name (`sloppy-jenkins:<job>`), or a hand-made one whose URL ends in `/project/<job>` (that's how it picked up the old powerprof webhook), and updates it instead of adding another. It always resends the secret, because GitLab clears a webhook's secret when its URL changes.
- If several webhooks could be the job's webhook, it stops, lists them and changes nothing. Delete the extra ones in GitLab and rerun.
- If GitLab rejects the change, the job's previous secret is restored. If GitLab's answer never arrives (for example, a timeout), GitLab may still have applied the change, so rerun the helper. Rerunning is always safe.

## 3b. Or... do it by hand

1. In the Jenkins job: **Configure -> Triggers -> Build when a change is pushed to GitLab -> Advanced -> Secret token -> Generate**, then **Save**. Copy the token.
2. In GitLab: **Settings -> Webhooks -> Add new webhook**.
   - URL: `https://<your-ngrok-domain>/project/<job name>` (for a job in a folder: `/project/<folder>/<job name>`).
   - **Secret token**: the token from step 1. The Jenkins plugin checks GitLab's *Secret token* (`X-Gitlab-Token`), not the newer *signing token* option.
   - Triggers: Push events, Merge request events.
3. Use **Test -> Push events** in GitLab and watch the Jenkins job start.

## Safety notes

- Keep Jenkins authentication on whenever ngrok exposes it.
- Use a different secret for each job. Never copy one job's secret into others, and never commit secrets, tokens or the ngrok authtoken.
- Stop ngrok (`Ctrl+C`) when you don't need external access.

---

_Happily written by Claude and Codex._
