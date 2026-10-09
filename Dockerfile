# Jenkins container development box
# Version :2.580.1-lts
#URL: https://hub.docker.com/layers/jenkins/jenkins/2.580.1-lts
#
# Purpose: To have an instance of a running jenkins instance and to help develop shared libraries, debug, work with internals of Jenkins without the need
# to hit a production server.
# Jenkins instance will be located at: C:\MNT\docker\jenkins\jenkins_home (in the compose.yaml file)

# BUILD WITH:
# `docker compose build`
# or with commnand line: `docker build -t sloppyjenkins:2.580.1-lts -f Dockerfile .`
#
# RUN WITH:
# docker compose up -d
# See compose.yaml for the image/container name, ports, and volume mapping.
# Re-run "docker compose up -d" (add --build after editing this Dockerfile or plugins.txt)
# any time you need to (re)start Jenkins.
#
FROM  jenkins/jenkins:2.580.1-lts AS jenkinsbaseimg

ENV JAVA_OPTS=-Djenkins.install.runSetupWizard=false
USER root
RUN apt-get -y update && apt-get -y upgrade
USER jenkins
########### Other third party install go here.

########### End of third party software installs.

FROM jenkinsbaseimg AS jenkinsplugininstalls
# Plugins install - rem out COPY/RUN steps for debug and disable the prod copy/run steps
COPY ./plugins/plugins.txt /usr/share/jenkins/ref/plugins.txt
RUN jenkins-plugin-cli --verbose -f /usr/share/jenkins/ref/plugins.txt

FROM jenkinsplugininstalls AS jenkinsinitscripts
# Jenkins runs EVERY script in $JENKINS_HOME/init.groovy.d on EVERY start, in file-name order
# (00-, 10-, 20-, 30-, 31-, 40-). The scripts are written to be idempotent; see init-scripts/README.txt.
COPY ./init-scripts/*.groovy /usr/share/jenkins/ref/init.groovy.d/

# The image owns init.groovy.d: on every container start the entrypoint deletes
# $JENKINS_HOME/init.groovy.d and copies the scripts above back in. A script removed from
# init-scripts/ disappears after a rebuild; a script placed by hand in the persistent home is deleted.
ENV PRE_CLEAR_INIT_GROOVY_D=true

# Managed job templates, read by 40-job-templates.groovy (kept outside ref/, so they aren't copied
# into the persistent home).
COPY ./job-templates/ /usr/share/jenkins/sloppy/job-templates/

# Return the user to standard user mode from root (above).
USER jenkins

