//Sets the default URL to the Jenkins instance under "Manage -> config"
import jenkins.model.JenkinsLocationConfiguration

def jenkinsUrl = "http://localhost:8787/"
def config = JenkinsLocationConfiguration.get()
config.setUrl(jenkinsUrl)
config.save()