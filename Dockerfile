# Jenkins container development box
# Purpose: To have an instance of a running jenkins instance and to help develop shared libraries, debug, work with internals of Jenkins without the need
# to hit a production server.
# Jenkins instance will be located at: 

# BUILD WITH: 
# docker build -t local_dev_jenkins_host .
#
# RUN WITH:
# mkdir C:\MNT\docker\jenkins\jenkins_home
# docker stop local_dev_jenkins 
# docker rm local_dev_jenkins
# docker run --name local_dev_jenkins -i -d -p 8787:8080 -p 50000:50000 -v C:\MNT\docker\jenkins\jenkins_home:/var/jenkins_home:rw local_dev_jenkins_host
# These steps are in setup.bat and can be re-ran anytime to restart jenkins by issuing "restartjenkins"
#
FROM jenkins/jenkins:lts as jenkinsbaseimg
ENV JAVA_OPTS -Djenkins.install.runSetupWizard=false
USER root
RUN apt-get -y update && apt-get -y upgrade
########### Other third party install go here.

########### End of third party software installs.

# Begin Jenkins manipulation
FROM jenkinsbaseimg as certstage

#Had PKI type cert error. Here's solution:
# Following website helped..
# https://www.java-samples.com/showtutorial.php?tutorialid=210
# Then I had to go to Jenkins.io update center and grab their cert. 
#COPY ./java-cert/cloud.cer /tmp/cloud.cer
#RUN keytool -storepass changeit -noprompt -list -keystore $JAVA_HOME/jre/lib/security/cacerts
#RUN keytool -storepass changeit -noprompt -import -alias myprivateroot2 -keystore $JAVA_HOME/jre/lib/security/cacerts -file /tmp/cloud.cer 
#RUN rm -rf /tmp/cloud.cer

FROM certstage as jenkinsplugininstalls

# #Plugins install - rem out COPY/RUN steps for debug and disable the prod copy/run steps
# #COPY plugins.txt /var/jenkins_home/plugins.txt
# #RUN jenkins-plugin-cli --verbose -f /var/jenkins_home/plugins.txt -Dcom.sun.security.enableAIAcaIssuers=true

COPY ./plugins/plugins.txt /usr/share/jenkins/ref/plugins.txt
RUN jenkins-plugin-cli --verbose -f /usr/share/jenkins/ref/plugins.txt

FROM jenkinsplugininstalls as jenkinsinitscripts
COPY ./init-scripts/setupusers.groovy /usr/share/jenkins/ref/init.groovy.d/setupusers.groovy
COPY ./init-scripts/executors.groovy /usr/share/jenkins/ref/init.groovy.d/executors.groovy
COPY ./init-scripts/security-cs.groovy /usr/share/jenkins/ref/init.groovy.d/security-cs.groovy
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

