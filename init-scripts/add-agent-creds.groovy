//Add username/password single entry.
import jenkins.*
import hudson.*
import hudson.model.*
import jenkins.model.*
import hudson.security.*
import com.cloudbees.plugins.credentials.*
import com.cloudbees.plugins.credentials.common.*
import com.cloudbees.plugins.credentials.domains.*
import com.cloudbees.plugins.credentials.CredentialsScope
import com.cloudbees.jenkins.plugins.sshcredentials.impl.*
import static com.cloudbees.plugins.credentials.CredentialsScope.GLOBAL
import hudson.util.Secret
import com.cloudbees.plugins.credentials.impl.UsernamePasswordCredentialsImpl
import org.jenkinsci.plugins.plaincredentials.impl.StringCredentialsImpl

CredentialsStore credentialsStore = SystemCredentialsProvider.getInstance().getStore()
globalDomain = Domain.global()

def boolean AddUserNamePasswordCredential(  CredentialsStore credentialsStore,
                                                                String id="ID:Cred",
                                                                String desc="DESC:Cred",
                                                                String username="username:Cred",
                                                                String passwd="passwd:Cred",
                                                                boolean secret=false )
{
    UsernamePasswordCredentialsImpl userPasswd = new UsernamePasswordCredentialsImpl(   CredentialsScope.GLOBAL,
                                                                                                                                                         id, 
                                                                                                                                                         desc,
                                                                                                                                                         username,
                                                                                                                                                         passwd ); 
    // Treat username as secret?
    userPasswd.setUsernameSecret(secret);

    if ( credentialsStore.addCredentials(globalDomain, userPasswd) )
    {
        userPasswd=null;
        return (true);
    }
    return (false);
}

if ( AddUserNamePasswordCredential(  credentialsStore,
                                                                "jenkins_agent_credentials", 
                                                                "Credentials for Jenkins agents", 
                                                                "jenkins_agent", 
                                                                "BLRwGW8hs_PnZ" ) ) 
     println ("SUCCESS! Credential added! \n");
else
     println ("FAIL! Credential added! If exist, we will fail \n");



