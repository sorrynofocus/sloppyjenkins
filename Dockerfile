# Jenkins container development box
# Version 2.574-jdk17 
#URL: https://hub.docker.com/layers/jenkins/jenkins/2.574/images/sha256-f03163e30f15c2b169b45c931b830620c839bd3d5a9ff2055b7944d9e49f1137
#
# Purpose: To have an instance of a running jenkins instance and to help develop shared libraries, debug, work with internals of Jenkins without the need
# to hit a production server.
# Jenkins instance will be located at: 

# BUILD WITH:
# docker compose build
#
# RUN WITH:
# docker compose up -d
# See compose.yaml for the image/container name, ports, and volume mapping.
# Re-run "docker compose up -d" (add --build after editing this Dockerfile or plugins.txt)
# any time you need to (re)start Jenkins.
#
# from  jenkins/jenkins:lts as jenkinsbaseimg
FROM  jenkins/jenkins:2.574 AS jenkinsbaseimg 

ENV JAVA_OPTS=-Djenkins.install.runSetupWizard=false
USER root
RUN apt-get -y update && apt-get -y upgrade
USER jenkins
########### Other third party install go here.

########### End of third party software installs.

# Begin Jenkins manipulation
FROM jenkinsbaseimg AS certstage

#Had PKI type cert error. Here's solution:
# Following website helped..
# https://www.java-samples.com/showtutorial.php?tutorialid=210
# Then I had to go to Jenkins.io update center and grab their cert. 
#COPY ./java-cert/cloud.cer /tmp/cloud.cer
#RUN keytool -storepass changeit -noprompt -list -keystore $JAVA_HOME/jre/lib/security/cacerts
#RUN keytool -storepass changeit -noprompt -import -alias myprivateroot2 -keystore $JAVA_HOME/jre/lib/security/cacerts -file /tmp/cloud.cer 
#RUN rm -rf /tmp/cloud.cer

FROM certstage AS jenkinsplugininstalls

# #Plugins install - rem out COPY/RUN steps for debug and disable the prod copy/run steps
# #COPY plugins.txt /var/jenkins_home/plugins.txt
# #RUN jenkins-plugin-cli --verbose -f /var/jenkins_home/plugins.txt -Dcom.sun.security.enableAIAcaIssuers=true

COPY ./plugins/plugins.txt /usr/share/jenkins/ref/plugins.txt
RUN jenkins-plugin-cli --verbose -f /usr/share/jenkins/ref/plugins.txt

FROM jenkinsplugininstalls AS jenkinsinitscripts
COPY ./init-scripts/setdefaulturl.groovy /usr/share/jenkins/ref/init.groovy.d/setdefaulturl.groovy
COPY ./init-scripts/setupusers.groovy /usr/share/jenkins/ref/init.groovy.d/setupusers.groovy
COPY ./init-scripts/executors.groovy /usr/share/jenkins/ref/init.groovy.d/executors.groovy
COPY ./init-scripts/security-cs.groovy /usr/share/jenkins/ref/init.groovy.d/security-cs.groovy
COPY ./init-scripts/add_agent_creds.groovy /usr/share/jenkins/ref/init.groovy.d/add_agent_creds.groovy
COPY ./init-scripts/create_ssh_agent.groovy /usr/share/jenkins/ref/init.groovy.d/create_ssh_agent.groovy
# # Since init.groovy.d works with scripts alphabeticaly, assign file name with z
# # This doesn't work, try to rem out the "Manual process to flag install completed" step
COPY ./init-scripts/zetupcomplete.groovy /usr/share/jenkins/ref/init.groovy.d/zetupcomplete.groovy
# # Manual process to flag install completed.
# #RUN echo 2.0 > /usr/share/jenkins/ref/jenkins.install.UpgradeWizard.state

# # Return the user to standard user mode from root (above).
USER jenkins


# # https://github.com/jitsi/jitsi-meet/issues/8243 helped
# # apt install ca-certificates-java
# # cd /usr/local/openjdk-8/jre/lib/security
# # mv cacerts cacerts.old
# # ln -s /etc/ssl/certs/java/cacerts cacerts

