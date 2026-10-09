@echo off
setlocal EnableExtensions
rem ---------------------------------------------------------------------------
rem Sloppy Jenkins (extra credit) - connect a Jenkins job to a GitLab project webhook.
rem
rem   gitlab-webhook.bat <jobPath> <group/project>
rem   gitlab-webhook.bat myproject me/myproject
rem
rem What it does:
rem   1. Generates a new random secret for this one job and stores it in the job's GitLab trigger.
rem   2. Creates or updates the GitLab project hook https://<ngrok-url>/project/<jobPath>
rem      with the same secret (GitLab "Secret token"). Rerun it whenever the ngrok URL changes.
rem   If GitLab fails, the job's previous secret is restored. Rerunning is always safe.
rem
rem Needs (never saved by this script):
rem   JENKINS_USER                     Jenkins user with Job/Configure on the job
rem   JENKINS_API_TOKEN, GITLAB_TOKEN  from the environment, or asked for with hidden input.
rem                                    GitLab token: personal access token, "api" scope, Maintainer on the project.
rem Tokens are only sent over https:// (plain http:// only to localhost).
rem Optional:
rem   JENKINS_URL   default http://localhost:8787/
rem   GITLAB_URL    default https://gitlab.com
rem   NGROK_URL     public https URL; otherwise read from ngrok's local API (127.0.0.1:4040)
rem
rem The job must have a GitLab trigger (create it from Templates/gitlab-pipeline-from-scm).
rem See docs\extra-credit-gitlab-webhooks.md.
rem ---------------------------------------------------------------------------

if "%~2"=="" (
    echo Usage: gitlab-webhook.bat ^<jobPath^> ^<group/project^>
    exit /b 1
)
call "%~dp0src\find-python.bat"
if errorlevel 1 exit /b 1
"%PY%" "%~dp0src\sloppy_tool.py" gitlab-webhook %*
exit /b %errorlevel%
