@echo off 
SETLOCAL EnableExtensions
mkdir C:\MNT\docker\jenkins\jenkins_home
doskey restartjenkins=docker stop local_dev_jenkins $T docker rm local_dev_jenkins $T docker run --name local_dev_jenkins -i -d -p 8787:8080 -p 50000:50000 -v C:\MNT\docker\jenkins\jenkins_home:/var/jenkins_home:rw local_dev_jenkins_host

echo *** SUCCESS!!! ***
echo ***
echo *** PORT: 8787
echo *** VOLUME: C:\MNT\docker\jenkins\jenkins_home (LOCAL) - /var/jenkins_home (SOURCE)
echo *** IMAGE: local_dev_jenkins_host
echo *** CONTAINER: local_dev_jenkins container
echo ***
echo *** 1. Type 'restartjenkins' to start or restart jenkins container.
echo ***
echo *** 2. In your browser migrate to: http://localhost:8787/ to enter your Jenkins instance.
echo ***
echo *** 3. If you need to get into Jenkins container, type:
echo ***     docker exec -it local_dev_jenkins /bin/bash
echo ***
echo *** 4. Data persists at the VOLUME stated above: C:\MNT\docker\jenkins\jenkins_home
echo ***


