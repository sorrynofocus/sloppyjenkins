//Create Windows Jenkins agent via SSH connection
//C Winters
import hudson.model.*
import jenkins.model.*
import hudson.slaves.*
import hudson.slaves.EnvironmentVariablesNodeProperty.Entry
import hudson.plugins.sshslaves.SSHLauncher
import hudson.plugins.sshslaves.verifiers.*

def hostCreateSSH(
                  String nodeHostName="newNodeCreateMe", 
                  String nodeHome="/home/jenkins", 
                  String nodeDescription="Just an awesome node to create!",
                  int numExecutors =1,
                  String nodeLabel ="node_label_temp_label",
                  String sshHost="192.0.0.1", 
                  String sshCreds="agent_service_account",
                  String sshJavaPath="/usr/bin/java"
                 )
{
    def jenkins = Jenkins.getInstance()

    SshHostKeyVerificationStrategy hostKeyVerificationStrategy = new NonVerifyingKeyVerificationStrategy()
        
    ComputerLauncher launcher = new hudson.plugins.sshslaves.SSHLauncher(
        sshHost, 
        22, 
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
    print("Create: ${agent} - ")
}


hostCreateSSH(
                        "windows_agent", 
                        "c:\\jenkins", 
                        "Node for Jenkins",
                        3,
                        "windows-label",          
                        "192.168.153.130",
                        "jenkins_agent_credentials",
                        "C:\\jdk-17.0.12+7\\bin\\java.exe"
              )

