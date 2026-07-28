# Snapshots shortName:version for every plugin installed on a running Jenkins
# instance and writes it to plugins-installed-snapshot.txt, in the same
# format plugins.txt uses. Review the snapshot, then copy the versions you
# want into plugins.txt to re-pin them.
param(
    [string]$JenkinsUrl = "http://localhost:8787",
    [string]$Username = $(if ($env:JENKINS_ADMIN_USERNAME) { $env:JENKINS_ADMIN_USERNAME } else { "admin" }),
    [string]$Password = $(if ($env:JENKINS_ADMIN_PASSWORD) { $env:JENKINS_ADMIN_PASSWORD } else { "password" })
)

$ErrorActionPreference = "Stop"

$JenkinsUrl = $JenkinsUrl.TrimEnd('/')
$pair = "${Username}:${Password}"
$basicAuth = [Convert]::ToBase64String([System.Text.Encoding]::ASCII.GetBytes($pair))
$headers = @{ Authorization = "Basic $basicAuth" }
$uri = "$JenkinsUrl/pluginManager/api/json?depth=1&tree=plugins[shortName,version]"

Write-Host "Fetching installed plugin list from $uri ..."
try {
    $response = Invoke-RestMethod -Uri $uri -Headers $headers -Method Get
} catch {
    Write-Error "Could not reach Jenkins at $JenkinsUrl (is the container running? are -Username/-Password correct?): $_"
    exit 1
}

$lines = $response.plugins |
    Sort-Object shortName |
    ForEach-Object { "$($_.shortName):$($_.version)" }

$outFile = Join-Path $PSScriptRoot "plugins-installed-snapshot.txt"
$lines | Set-Content -Path $outFile -Encoding ascii

Write-Host "Wrote $($lines.Count) plugin entries to $outFile"
Write-Host "Review it, then copy the versions you want into plugins.txt to re-pin them."
