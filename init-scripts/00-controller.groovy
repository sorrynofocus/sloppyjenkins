// Controller basics. Runs on EVERY Jenkins start, so every step is idempotent.
//  - Controller keeps 0 executors (builds run on agents).
//  - CSRF protection is on.
//  - The setup wizard is marked complete (replaces the old zetupcomplete.groovy).
//  - The Jenkins URL is only set when it is empty, or when SLOPPY_JENKINS_URL is supplied,
//    so a URL changed in Manage Jenkins -> System survives restarts.
import hudson.security.csrf.DefaultCrumbIssuer
import jenkins.install.InstallState
import jenkins.model.Jenkins
import jenkins.model.JenkinsLocationConfiguration

def jenkins = Jenkins.get()
def changed = false

if (jenkins.numExecutors != 0) {
    jenkins.numExecutors = 0
    changed = true
    println('[sloppy] Controller executors set to 0.')
}

if (jenkins.crumbIssuer == null) {
    jenkins.crumbIssuer = new DefaultCrumbIssuer(true)
    changed = true
    println('[sloppy] CSRF protection enabled.')
}

if (!jenkins.installState.isSetupComplete()) {
    jenkins.installState = InstallState.INITIAL_SETUP_COMPLETED
    println('[sloppy] Setup wizard marked complete.')
}

if (changed) {
    jenkins.save()
}

def location = JenkinsLocationConfiguration.get()
def requestedUrl = System.getenv('SLOPPY_JENKINS_URL')?.trim()
if (requestedUrl) {
    if (!requestedUrl.endsWith('/')) {
        requestedUrl += '/'
    }
    if (location.url != requestedUrl) {
        location.url = requestedUrl
        location.save()
        println("[sloppy] Jenkins URL set to ${requestedUrl} (from SLOPPY_JENKINS_URL).")
    }
} else if (!location.url) {
    location.url = 'http://localhost:8787/'
    location.save()
    println('[sloppy] Jenkins URL was empty; set to http://localhost:8787/.')
}
