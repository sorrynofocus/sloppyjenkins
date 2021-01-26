##  Jenkins container development box

### Purpose: To have an instance of a running jenkins instance and to help develop shared libraries, debug, work with internals of Jenkins without the need to hit a production server.

- 🔭 Write shared libraries easier by throwing them into working-libs folder and restarting jenkins locally 
- 🌱 Run jenkins and learn internals 🤣
- 👯 Collaborate with others, or be a lonewolf!
- 🥅 Goals: ON A LOCAL POINT OF VIEW: Create shared libaries easier, work with helm, work with plugins, work with jobs, and many more.
- ⚡ Facts: All your code-bass are belong to us! Well, after you code review it 🤣 🤣 🤣
- ✍️ Write your own plugins and blow it up, safely, in the container!

## GETTING STARTED

The project's source will do *everything* for you. At least, *try to*. It will build the docker image, configfure jenkins, install recommended plugins, set up an admin account, etc. It will get you started with Jenkins enough to take out most of the hassle. As the project grows, more automated things will be entered. 

In order to get started, you'll need 3 small prerequisites. And, it shouldn't be painful. 

1. You'll need Internet access.
2. Command prompt (Or Windows Terminal you can get at Windows Store [⚡ better ⚡]). Do not close the command prompt. 
3. Install Docker for Desktop for Windows. This project is a linux image/container so WSL will be enabled. Docker Desktop install will guide you through this.

        Once Docker is setup, we will need to switch to Linux containers to use this project. 
        You can do this via right clicking on the white docker whale icon and choose 
        "Switch to Linux containers".

        OR

        Drop to a command prompt, and enter:
        "c:\Program Files\Docker\Docker\dockercli" -SwitchLinuxEngine

        Note: You can later switch back to Windows containers via UI or 
        "c:\Program Files\Docker\Docker\dockercli" -SwitchWindowsEngine

### If you have not built the image
1. Once you've switched to Linux containers and downloaded the project's source files, enter the projects' directory and drop to a command prompt. 

        For example: If you copied the project's source to C:\docker-dynamic-jenkins-work, 
        switch to this directory by typing:

        cd C:\docker-dynamic-jenkins-work

2. Type: **build-docker-jenkins-cont.bat**

3. Get Coffee, or tea. Build time: ~15 minutes if never built, 3 minutes if previous build exist.

4. Jenkins docker image will begin. 


5. Once **success** build is complete, type **restartjenkins**<BR>

    > You'll witness feed back, something similar to this:

    > c:\docker-dynamic-jenkins-work>f256d1fd1e62d8648cebb94cef09ec3b52b754b05940f67c1c6955871246b664
    This means a container has started. You can validate this by typing *docker ps* and validating *local_dev_jenkins_host* is running.
<BR>
<BR>
If NOT success, then examine the README files in the subfolders to help troubleshoot.

6. In your browser migrate to: http://localhost:8787/  (please be patient. Jenkins is starting...)
<BR>
NOTE: Jenkins admin user/password is *admin/password*

7. Jenkins is ready!

NOTE: Don't close your command prompt or the alias *restartjenkins* will disappear. You'll need this in case you need to restart the Jenkins container when modifying files requiring a restart. IF you cannot use the *restartjenkins* alias, then run the *dsetup.bat* to restore it. This will also destroy the container and restart, but Jenkins data will not be deleted.


### If you've built the image

1. Open a command prompt.

2. Move to this project's directory (where this project lives)

3. Type **dsetup.bat**
<BR>
    > If your Jenkins container is currently running, there's no need for step 4. Skip to step 5!

4. Type **restartjenkins**
    > You'll witness feed back, something similar to this:

    > c:\docker-dynamic-jenkins-work>f256d1fd1e62d8648cebb94cef09ec3b52b754b05940f67c1c6955871246b664
    This means a container has started. You can validate this by typing *docker ps* and validating *local_dev_jenkins_host* is running.
<BR>
<BR>
If NOT success, then examine the README files in the subfolders to help troubleshoot.

5. In your browser migrate to: http://localhost:8787/  (please be patient. Jenkins is starting...)
<BR>
NOTE: Jenkins admin user/password is *admin/password*

6. Jenkins is ready!


### ...And a final word

- While Jenkins is running (obvious... 🤣 🤣 🤣 ): 
    - All data is persisted in the location *C:\MNT\docker\jenkins\jenkins_home* 
    - If you need to restart Jenkins, simply type type *restartjenkins* at the command prompt you've left open.

- If need access to the Jenkins container, type:
    docker exec -it local_dev_jenkins /bin/bash

- This container is a Debian GNU/Linux 9 (stretch) image with latest Jenkins. Also installed is OpenJDK 1.8.0_242. Removing the USER jenkins from Dockerfile will keep root which is not recommended.

- To end your Jenkins container experience, type: **docker kill local_dev_jenkins**



