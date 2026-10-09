// Creates a Windows build node that connects to Jenkins as an inbound agent.
// No agent credential is stored here: Jenkins generates a per-node secret.
// Runs on EVERY Jenkins start: an existing node is never modified (create-if-missing).
//
// Overrides (environment variables on the controller container):
//   JENKINS_WINDOWS_AGENT_NAME       default windows_build_agent
//   JENKINS_WINDOWS_AGENT_WORKDIR    default C:\Jenkins
//   JENKINS_WINDOWS_AGENT_LABELS     default windows-label
//   JENKINS_WINDOWS_AGENT_EXECUTORS  default 1
//
// The connection mode is chosen by the Windows command (tools\start-agent.bat passes -webSocket).
// The launcher's webSocket flag below only makes the node page display the matching command.
import hudson.model.Node
import hudson.slaves.DumbSlave
import hudson.slaves.JNLPLauncher
import hudson.slaves.RetentionStrategy
import jenkins.model.Jenkins

def jenkins = Jenkins.get()
def nodeName = System.getenv('JENKINS_WINDOWS_AGENT_NAME') ?: 'windows_build_agent'

if (jenkins.getNode(nodeName) != null) {
    println("[sloppy] Jenkins node '${nodeName}' already exists; leaving its persistent configuration unchanged.")
    return
}

def remoteFs = System.getenv('JENKINS_WINDOWS_AGENT_WORKDIR') ?: 'C:\\Jenkins'
def labels = System.getenv('JENKINS_WINDOWS_AGENT_LABELS') ?: 'windows-label'
def executorText = System.getenv('JENKINS_WINDOWS_AGENT_EXECUTORS') ?: '1'
def executorCount

try {
    executorCount = Integer.parseInt(executorText)
} catch (NumberFormatException ignored) {
    throw new IllegalArgumentException("JENKINS_WINDOWS_AGENT_EXECUTORS must be an integer, got '${executorText}'.")
}

if (executorCount < 1) {
    throw new IllegalArgumentException('JENKINS_WINDOWS_AGENT_EXECUTORS must be at least 1.')
}

def launcher = new JNLPLauncher()
launcher.webSocket = true

def agent = new DumbSlave(nodeName, remoteFs, launcher)
agent.nodeDescription = 'Local Windows build agent (inbound connection). Start it with tools\\start-agent.bat.'
agent.numExecutors = executorCount
agent.labelString = labels
agent.mode = Node.Mode.EXCLUSIVE
agent.retentionStrategy = new RetentionStrategy.Always()

jenkins.addNode(agent)
jenkins.save()
println("[sloppy] Created inbound Jenkins node '${nodeName}' with ${executorCount} executor(s), labels '${labels}', root '${remoteFs}'.")
