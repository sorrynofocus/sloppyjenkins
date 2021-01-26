@echo off
echo [BUILDING DOCKER IMAGE FOR JENKINS INSTANCE]

docker rmi -f local_dev_jenkins_host
docker build -t local_dev_jenkins_host .

call dsetup.bat

echo ** DOCKER IMAGE COMPILED!!!! ***
echo **********************
echo ** SHOULD ERRORS APPEAR, CONSULT README FILES IN SUBDIRECTORIES ** 
echo **
