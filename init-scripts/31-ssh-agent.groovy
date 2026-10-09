//Create Windows Jenkins agent via SSH connection
//C Winters
//
// Optional SSH-launched build node. Runs on EVERY Jenkins start, but does nothing unless
// SLOPPY_SSH_AGENT_HOST is set in .env (silent when it is not). Creates the node only when it is
// missing; an existing node is never changed (edit it in Manage Jenkins -> Nodes).
//
// Settings (.env):
//   SLOPPY_SSH_AGENT_HOST       required: host name or IP of the machine running an SSH server
//   SLOPPY_SSH_AGENT_PORT       default 22
//   SLOPPY_SSH_AGENT_NAME       default windows_agent
//   SLOPPY_SSH_AGENT_ROOT       default c:\jenkins (remote root directory on that machine)
//   SLOPPY_SSH_AGENT_EXECUTORS  default 3
//   SLOPPY_SSH_AGENT_LABELS     default windows-label. NOTE: the inbound node (30-windows-agent.groovy)
//                               uses the same label, so jobs asking for windows-label may run on either
//                               node. Use a different label if they must stay apart.
//   SLOPPY_SSH_AGENT_JAVA       default C:\jdk-latest\bin\java.exe (Java 21+ on the SSH machine)
//   SLOPPY_SSH_AGENT_CRED_ID    default jenkins_agent_credentials: the "Username with password"
//                               credential used to log in. Create it in Manage Jenkins -> Credentials,
//                               or let 20-username-credentials.groovy create it from a SLOPPY_CRED_<n>
//                               set with that ID (20- runs before this script).
//
// Host keys are verified: on the first connection Jenkins waits until an admin trusts the agent's
// host key (Manage Jenkins -> Nodes -> <node> -> Trust SSH Host Key).
import com.cloudbees.plugins.credentials.CredentialsProvider
import com.cloudbees.plugins.credentials.common.StandardUsernameCredentials
import hudson.model.*
import jenkins.model.*
import hudson.slaves.*
import hudson.plugins.sshslaves.SSHLauncher
import hudson.plugins.sshslaves.verifiers.*

// Written as a closure, not a method: Groovy names a script's classes after the file, and a method in
// "31-ssh-agent.groovy" would need a nested class named "31-ssh-agent$hostCreateSSH", which Java rejects
// (a class name cannot start with a digit or contain "-"). Closures in a script do not hit this.
def hostCreateSSH = {
                  String nodeHostName="newNodeCreateMe",
                  String nodeHome="/home/jenkins",
                  String nodeDescription="Just an awesome node to create!",
                  int numExecutors =1,
                  String nodeLabel ="node_label_temp_label",
                  String sshHost="192.0.0.1",
                  int sshPort=22,
                  String sshCreds="agent_service_account",
                  String sshJavaPath="/usr/bin/java"
                  ->
    def jenkins = Jenkins.get()

    if (jenkins.getNode(nodeHostName) != null) {
        println("[sloppy] SSH node '${nodeHostName}' already exists; leaving it unchanged.")
        return
    }

    // The node can be created before its credential exists, but it cannot connect until it does.
    def credentialExists = CredentialsProvider.lookupCredentials(
            StandardUsernameCredentials, jenkins, null, null).any { it.id == sshCreds }
    if (!credentialExists) {
        println("[sloppy] WARNING: SSH node '${nodeHostName}' uses credential '${sshCreds}', which does not exist yet. " +
                'Create it (Manage Jenkins -> Credentials, or a SLOPPY_CRED_<n> set in .env) before the node can connect.')
    }

    // Host keys are verified: on the first connection Jenkins waits until an admin trusts the agent's
    // host key (Manage Jenkins -> Nodes -> <node> -> Trust SSH Host Key). Accepting any key
    // (NonVerifyingKeyVerificationStrategy) would let another machine impersonate the agent and
    // receive the agent credential, so it is deliberately not used here.
    SshHostKeyVerificationStrategy hostKeyVerificationStrategy = new ManuallyTrustedKeyVerificationStrategy(true)

    ComputerLauncher launcher = new hudson.plugins.sshslaves.SSHLauncher(
        sshHost,
        sshPort,
        sshCreds,
        (String)null,
        sshJavaPath,
        (String)null,
        (String)null,
        (Integer)null,
        (Integer)null,
        (Integer)null,
        hostKeyVerificationStrategy
            )

    Slave agent = new DumbSlave(
                                 nodeHostName,
                                nodeHome,
                                launcher
                                )

    agent.nodeDescription = nodeDescription
    agent.numExecutors = numExecutors
    agent.labelString = nodeLabel
    agent.mode = Node.Mode.NORMAL
    agent.retentionStrategy = new RetentionStrategy.Always()
    jenkins.addNode(agent)
    println("[sloppy] Created SSH node '${nodeHostName}' -> ${sshHost}:${sshPort} (labels '${nodeLabel}', credential '${sshCreds}').")
}

def setting = { String name, String fallback -> System.getenv(name)?.trim() ?: fallback }

def sshHost = setting('SLOPPY_SSH_AGENT_HOST', null)
if (!sshHost) {
    return   // SSH node not configured: nothing to do, nothing to say
}

// At most 9 digits are converted: that always fits in an int, so an oversized value gets the warning
// below instead of throwing (an exception here would make Jenkins skip all later startup scripts).
def numberSetting = { String name, String fallback, int min, int max ->
    def text = setting(name, fallback)
    Integer number = (text ==~ /\d{1,9}/) ? (text as Integer) : null
    if (number == null || number < min || number > max) {
        println("[sloppy] WARNING: ${name}='${text}' is not a number from ${min} to ${max}; SSH node not created.")
        return null
    }
    return number
}
def executors = numberSetting('SLOPPY_SSH_AGENT_EXECUTORS', '3', 1, 100)
def port = numberSetting('SLOPPY_SSH_AGENT_PORT', '22', 1, 65535)
if (executors == null || port == null) {
    return
}

// jdk-latest should always have the latest and tested copy into C:\jdk-latest
// this will keep from having to update the Java path manually in the future
// try/catch: if Jenkins rejects the node (for example an invalid name), log it and let the later
// startup scripts still run. Only the error type is printed.
try {
    hostCreateSSH(
                        setting('SLOPPY_SSH_AGENT_NAME', "windows_agent"),
                        setting('SLOPPY_SSH_AGENT_ROOT', "c:\\jenkins"),
                        "Node for Jenkins",
                        executors,
                        setting('SLOPPY_SSH_AGENT_LABELS', "windows-label"),
                        sshHost,
                        port,
                        setting('SLOPPY_SSH_AGENT_CRED_ID', "jenkins_agent_credentials"),
                        setting('SLOPPY_SSH_AGENT_JAVA', "C:\\jdk-latest\\bin\\java.exe")
              )
} catch (Exception e) {
    println("[sloppy] WARNING: SSH node not created: ${e.class.simpleName}. Check the SLOPPY_SSH_AGENT_* values in .env.")
}
