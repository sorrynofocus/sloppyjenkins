@echo off
setlocal EnableExtensions
rem ---------------------------------------------------------------------------
rem Sloppy Jenkins - create a real Pipeline job from a template.
rem
rem   new-job.bat <path/name> <generic|gitlab> "<repoUrl>" [branch] [credentialId]
rem
rem   new-job.bat myproject generic "https://gitlab.com/me/myproject.git" main my-repo-cred
rem   new-job.bat Team/myproject gitlab "https://gitlab.com/me/myproject.git"
rem
rem Copies Templates/pipeline-from-scm (generic) or Templates/gitlab-pipeline-from-scm (gitlab),
rem sets the repository, branch (default main) and credential (default scm-credentials),
rem and enables the new job. Existing jobs are never overwritten. A folder in the path must already exist.
rem Quote the repository URL.
rem
rem Needs JENKINS_USER. The API token (Jenkins -> your user -> Security -> API Token) comes from
rem JENKINS_API_TOKEN or is asked for with hidden input. JENKINS_URL defaults to http://localhost:8787/
rem Permissions: Overall/Read, Job/Configure on the template (needed to read its config.xml; the optional
rem Extended Read permission is not installed), and Job/Create on the destination folder.
rem ---------------------------------------------------------------------------

if "%~3"=="" (
    echo Usage: new-job.bat ^<path/name^> ^<generic^|gitlab^> "<repoUrl>" [branch] [credentialId]
    exit /b 1
)
call "%~dp0src\find-python.bat"
if errorlevel 1 exit /b 1
"%PY%" "%~dp0src\sloppy_tool.py" new-job %*
exit /b %errorlevel%
