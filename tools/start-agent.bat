@echo off
setlocal EnableExtensions
rem ---------------------------------------------------------------------------
rem Sloppy Jenkins - start the Windows inbound build agent.
rem Run it yourself from Command Prompt. Ctrl+C stops the agent.
rem
rem   start-agent.bat                 connect the agent
rem   start-agent.bat /resetsecret    forget the saved secret and ask for it again
rem
rem Optional settings (set them before running):
rem   JENKINS_URL        default http://localhost:8787/
rem   AGENT_NAME         default windows_build_agent
rem   AGENT_ROOT         default C:\Jenkins. Keep it the same as the node's "Remote root directory"
rem                      in Jenkins: builds run in <Remote root>\workspace, whatever AGENT_ROOT says.
rem   JENKINS_USER       when set, a missing secret is fetched from Jenkins instead of pasted. The API
rem                      token comes from JENKINS_API_TOKEN or is asked for with hidden input.
rem
rem agent.jar is only downloaded when it is missing or Jenkins has a newer one (after a Jenkins upgrade).
rem
rem The secret is asked for (or fetched) once and saved; later runs reuse the saved secret and need no
rem API token. After recreating jenkins_home or the node, run start-agent.bat /resetsecret.
rem The secret is stored in %AGENT_ROOT%\secrets\agent-secret.txt. That folder is locked to your
rem Windows account before the secret is written; if that cannot be guaranteed the script stops and
rem deletes the secret. It is passed to the agent as -secret @file, never on a command line.
rem ---------------------------------------------------------------------------

if not defined JENKINS_URL set "JENKINS_URL=http://localhost:8787/"
if not "%JENKINS_URL:~-1%"=="/" set "JENKINS_URL=%JENKINS_URL%/"
if not defined AGENT_NAME set "AGENT_NAME=windows_build_agent"
if not defined AGENT_ROOT set "AGENT_ROOT=C:\Jenkins"
set "TOOL=%~dp0src\sloppy_tool.py"
set "SECRET_DIR=%AGENT_ROOT%\secrets"
set "SECRET_FILE=%SECRET_DIR%\agent-secret.txt"
set "ME=%USERDOMAIN%\%USERNAME%"

call "%~dp0src\find-python.bat"
if errorlevel 1 exit /b 1

where java >nul 2>nul
if errorlevel 1 (
    echo ERROR: java was not found on PATH. Install Java 21 or newer, for example from https://adoptium.net/
    exit /b 1
)
"%PY%" "%TOOL%" check-java
if errorlevel 1 (
    echo ERROR: Java 21 or newer is required. Check "java -version".
    exit /b 1
)

rem agent.jar is downloaded from, and the secret sent to, JENKINS_URL: https only, or http to this machine.
"%PY%" "%TOOL%" check-url "%JENKINS_URL%" JENKINS_URL
if errorlevel 1 exit /b 1

if not exist "%AGENT_ROOT%\" (
    mkdir "%AGENT_ROOT%"
    if errorlevel 1 (
        echo ERROR: could not create %AGENT_ROOT%.
        exit /b 1
    )
)

rem -R gives agent.jar the file time Jenkins reports, and -z sends that time back. When Jenkins' copy
rem is not newer it answers "304 Not Modified" and curl writes nothing, so agent.jar is kept.
set "AGENT_JAR=%AGENT_ROOT%\agent.jar"
if exist "%AGENT_JAR%.new" del /f /q "%AGENT_JAR%.new"
set "IF_NEWER="
if exist "%AGENT_JAR%" set IF_NEWER=-z "%AGENT_JAR%"
echo Getting agent.jar from %JENKINS_URL% (only if missing or newer) ...
curl.exe -fsS -R %IF_NEWER% -o "%AGENT_JAR%.new" "%JENKINS_URL%jnlpJars/agent.jar"
if errorlevel 1 (
    if exist "%AGENT_JAR%.new" del /f /q "%AGENT_JAR%.new"
    echo ERROR: could not download agent.jar. Is Jenkins running at %JENKINS_URL% ?
    exit /b 3
)
rem Only a non-empty download replaces agent.jar.
set "JAR_SIZE=0"
if exist "%AGENT_JAR%.new" for %%F in ("%AGENT_JAR%.new") do set "JAR_SIZE=%%~zF"
if not "%JAR_SIZE%"=="0" (
    move /y "%AGENT_JAR%.new" "%AGENT_JAR%" >nul
    echo agent.jar downloaded.
) else (
    if exist "%AGENT_JAR%.new" del /f /q "%AGENT_JAR%.new"
    echo agent.jar is up to date.
)

rem Lock the secrets folder to the current user BEFORE any secret is written into it.
if not exist "%SECRET_DIR%\" (
    mkdir "%SECRET_DIR%"
    if errorlevel 1 (
        echo ERROR: could not create %SECRET_DIR%.
        exit /b 1
    )
)
icacls "%SECRET_DIR%" /inheritance:r /grant:r "%ME%:(OI)(CI)F" >nul
if errorlevel 1 (
    echo ERROR: could not restrict %SECRET_DIR% to %ME%. The agent secret was not written.
    exit /b 1
)
rem /inheritance:r and /grant:r keep explicit permissions of OTHER accounts, so verify the folder itself.
call :only_me "%SECRET_DIR%"
if errorlevel 1 (
    if exist "%SECRET_FILE%" del /f /q "%SECRET_FILE%"
    echo ERROR: other accounts have permissions on %SECRET_DIR%.
    echo No secret was written ^(an existing one was deleted^) and the agent was not started.
    echo Delete the folder %SECRET_DIR% and run this script again; it recreates the folder locked to %ME%.
    exit /b 1
)

if /i "%~1"=="/resetsecret" (
    if exist "%SECRET_FILE%" del /f /q "%SECRET_FILE%"
)

if exist "%SECRET_FILE%" (
    echo Using the saved agent secret. If Jenkins rejects it, run: start-agent.bat /resetsecret
    goto secret_ready
)
if defined JENKINS_USER goto fetch_secret
echo.
echo The agent secret is shown in Jenkins: Manage Jenkins -^> Nodes -^> %AGENT_NAME%
echo (the long value after -secret in the command Jenkins displays).
"%PY%" "%TOOL%" prompt-secret "%SECRET_FILE%"
if errorlevel 1 exit /b 1
goto secret_ready

:fetch_secret
"%PY%" "%TOOL%" agent-secret "%AGENT_NAME%" "%SECRET_FILE%"
if errorlevel 1 exit /b %errorlevel%

:secret_ready
rem Fail closed: the secret file must be accessible to the current user only.
icacls "%SECRET_FILE%" /inheritance:r /grant:r "%ME%:F" >nul
if errorlevel 1 goto acl_failed
call :only_me "%SECRET_FILE%"
if errorlevel 1 goto acl_failed

echo Starting agent "%AGENT_NAME%" against %JENKINS_URL% (work dir %AGENT_ROOT%). Press Ctrl+C to stop.
echo If it keeps printing "Failed to connect: Handshake error", the secret is wrong:
echo press Ctrl+C and run: start-agent.bat /resetsecret
java -jar "%AGENT_JAR%" -url "%JENKINS_URL%" -name "%AGENT_NAME%" -secret "@%SECRET_FILE%" -webSocket -workDir "%AGENT_ROOT%"
set "RC=%errorlevel%"
echo.
echo Agent stopped (exit code %RC%). If Jenkins rejected the secret, run: start-agent.bat /resetsecret
exit /b %RC%

:acl_failed
del /f /q "%SECRET_FILE%" >nul 2>nul
echo ERROR: could not make %SECRET_FILE% readable only by %ME%.
echo The secret was deleted and the agent was not started. Check the folder permissions and try again.
exit /b 1

:only_me
rem errorlevel 0 when only the current user has permissions on %1, 1 otherwise (or when icacls fails).
icacls %1 >nul 2>nul
if errorlevel 1 exit /b 1
icacls %1 | findstr /c:":(" | findstr /v /i /l /c:"%ME%:(" >nul
if not errorlevel 1 exit /b 1
exit /b 0
