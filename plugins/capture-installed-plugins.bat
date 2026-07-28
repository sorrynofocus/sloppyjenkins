@echo off
echo [CAPTURING INSTALLED PLUGIN VERSIONS FROM RUNNING JENKINS]

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0capture-installed-plugins.ps1" %*

echo **********************
echo ** Review plugins\plugins-installed-snapshot.txt, then copy the versions
echo ** you want into plugins\plugins.txt to re-pin them.
echo **
