# Extra credit: GitLab webhooks through ngrok

This is optional. Sloppy Jenkins works without it. It shows one way to let a GitLab.com project start a Jenkins build when you push, using ngrok to reach your local Jenkins.

```text
GitLab.com -> https://<your-ngrok-domain>/project/<job> -> localhost:8787 -> Jenkins container
```

## 1. Prerequisites

- Jenkins running, and ngrok running: `ngrok http 8787` (see the main README). A reserved ngrok domain keeps the URL stable.
- Python 3.10 or newer on the Windows host. The batch helpers use only Python's standard library.
- A Jenkins credential that can read the repository (for GitLab: a project or personal access token with `read_repository`, stored as Username with password).

## 2. Create the job from the GitLab template

In Jenkins: **New Item**, then **Copy from** `Templates/gitlab-pipeline-from-scm`. Set the repository URL, credential and branch, then enable and save the job. Or from Command Prompt:

```cmd
set JENKINS_USER=admin
tools\new-job.bat myproject gitlab "https://gitlab.com/me/myproject.git" main my-repo-credential
```

The helper asks for your Jenkins API token with hidden input.

**The new job is not webhook-ready yet.** Its GitLab trigger has no secret token. While it's empty, and the global "Enable authentication for '/project' end-point" setting is on (the default, under Manage Jenkins -> System -> GitLab), GitLab can only trigger the job with Jenkins user/API-token credentials. Each job should get its own secret token instead, using either of the two options below.

## 3a. Let the helper connect both sides

```cmd
set JENKINS_USER=admin
tools\gitlab-webhook.bat myproject me/myproject
```

- The helper asks for your Jenkins API token and then your GitLab token, both with hidden input. You can set `JENKINS_API_TOKEN` and `GITLAB_TOKEN` first instead, but don't type tokens with `set /p`, because it shows them on screen.
- The GitLab token is a personal access token with the **api** scope. Your account needs **Maintainer** on the project to manage webhooks. It is used only for this run; the helper never saves or prints it.
- Tokens are only sent over `https://`. Plain `http://` is allowed only for `localhost`, so a self-managed GitLab must use HTTPS.
- The helper:
  1. generates a new random secret for this one job and stores it in the job's GitLab trigger;
  2. creates the GitLab project webhook `https://<ngrok-url>/project/myproject` with that secret, for push, merge request and comment events.

  It finds the ngrok URL through ngrok's local API, or you can `set NGROK_URL=https://your-domain.ngrok-free.dev`.
- **Run it again whenever the ngrok URL changes.** It finds its own webhook by name (`sloppy-jenkins:<job>`) and updates it instead of adding another. It always resends the secret, because GitLab clears a webhook's secret when its URL changes.
- If several webhooks could be the job's webhook, it stops, lists them and changes nothing. Delete the extra ones in GitLab and rerun.
- If GitLab rejects the change, the job's previous secret is restored. If GitLab's answer never arrives (for example, a timeout), GitLab may still have applied the change, so rerun the helper. Rerunning is always safe.
- Self-managed GitLab: `set GITLAB_URL=https://gitlab.example.com`.

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
