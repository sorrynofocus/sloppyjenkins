##  Sloppy Jenkins 
### Local Jenkins Docker Container development box

Updated: 2026.07.28

### Purpose: To have a local jenkins instance; to develop shared libraries, debug, and work with internals. All this glory without the need to hit a production server.

- Run jenkins and learn internals 
- Write your own plugins... and blow it up, safely, in the container!

## Project stats:
- Linux Debian GNU/Linux 13 (trixie)
- OpenJDK Runtime Environment 21.0.11 - [openjdk.org/projects/jdk/21](https://openjdk.org/projects/jdk/21/)
- Jenkins 2.574 - [hub.docker.com/layers/jenkins/jenkins/2.574](https://hub.docker.com/layers/jenkins/jenkins/2.574/images/sha256-f03163e30f15c2b169b45c931b830620c839bd3d5a9ff2055b7944d9e49f1137)

## Build instructions

The project's source will do *everything* for you. At least, *try to*. 

The project will:

- Build the docker image
- Configure jenkins
- Install recommended plugins (see [plugins/plugins.txt](plugins/plugins.txt) and [plugins/README.txt](plugins/README.txt))
- Set up an admin account (see [init-scripts/](init-scripts/) and [init-scripts/README.txt](init-scripts/README.txt))
- Get you started with a Docker container with a local Jenkins instance. This is enough to get a local server up and running with persistent server data.

### Prerequisites

**_NOTE:_** These instructions assume a **Windows** host. If you're on **Linux** or **macOS**, adjust accordingly: Docker there only runs Linux containers already (there's no container-mode switch, so you can skip step 3. `Docker for Desktop for Windows`). You'll also need to change the paths in `compose.yaml` (example: `C:\MNT\docker\jenkins\jenkins_home`) to a Linux/macOS-style path such as `~/mnt/docker/jenkins/jenkins_home`.

1. You'll need `internet access`.

2. `Command prompt` (or Windows Terminal ).

3. `Docker for Desktop for Windows`. This project was constructed as a linux image/container. Docker Desktop install is easy to install.

        Once Docker is setup, we will need to switch to Linux containers to use this project. 
        You can do this via right clicking on the white docker whale icon and choose 
        "Switch to Linux containers".

        OR

        At the command prompt, and enter:
        "c:\Program Files\Docker\Docker\dockercli" -SwitchLinuxEngine

        Note: You can later switch back to Windows containers via UI or 
        "c:\Program Files\Docker\Docker\dockercli" -SwitchWindowsEngine

### Build the initial Docker image
1. Once you've switched to Linux containers and downloaded this project's source files, enter the projects' directory and drop to a command prompt. 

        For example: If you copied the project's source to C:\docker-dynamic-jenkins-work, 
        switch to this directory by typing:

        cd C:\docker-dynamic-jenkins-work

2. Type: **docker compose build**

    Get coffee, or tea. Build time: ~10 minutes if never built, 3 minutes if previous build exist. Jenkins docker image will be completed shortly. 

3. Once **success** build is complete, type `docker compose up -d`<BR>

    > You'll witness feed back, something similar to this:

    > Network docker-dynamic-jenkins-work_default  Created
    > Container local_dev_jenkins  Started

    This means a container has started. You can validate this by typing *docker ps* and validating *local_dev_jenkins* is running.
<BR>
<BR>
If NOT success, then examine the README files in the subfolders to help troubleshoot. Typical issue appear in the plugin folders. There's good documentation to debug the container. 

Note: Also, it may take some time to bring up the Jenkins server. It may appear the server is not running. Wait until you see the familiar message:

```
Please wait while Jenkins is getting ready to work ...
Your browser will reload automatically when Jenkins is ready.
```

4. In your browser migrate to: http://localhost:8787/  (please be patient. Jenkins is starting...)
<BR>

    > NOTE: Jenkins admin user/password is *admin/password*


Jenkins is ready!

NOTE: `docker compose` reads `compose.yaml` from this project directory - there's no alias to set up and nothing to lose by closing your command prompt. Any time you need to start, stop, or rebuild Jenkins, just `cd` back into this directory and run the relevant `docker compose` command again.


### Revisting the Jenkins instance from the container.

Once the image has been built, you can run the container at any time to ready the Jenkins instance. If you followed the instructions above, Jenkins will be setup and ready to run. If you closed down the container, or perhaps rebooted the Jenkins instance, you can easily run the instance again because you have a working image to run a new container.
Because the data is persistent, your Jenkins instance will retain the previous configuration. To revisit your Jenkins instance at a later time, you do so by these easy instructions:

1. Open a command prompt.

2. Move to this project's directory (where this project lives)

3. Type **docker compose up -d**
<BR>
    > If your Jenkins container is already running, this is a no-op - Compose only (re)creates the container when the image or config has actually changed.

    You'll witness feed back, something similar to this:

    `Container local_dev_jenkins  Started`

    This means _a container has started_! You can validate this by typing `docker ps` and validating `local_dev_jenkins` is running.

    If NOT success, then examine the logs and `README` files in the plugin subfolders to help troubleshoot.

    The docker logs can also provide useful info ofr troubleshooting. Here's a few commands for logging:

    _Show the last 100 lines of the Jenkins container logs:_

    `docker compose logs --tail 100`
    
    _Show the live logs of the Jenkins container:_
    `docker compose logs -f`
    

4. In your browser migrate to: http://localhost:8787/  (please be patient. Jenkins is starting...)
<BR>
NOTE: Jenkins admin user/password is `admin/password`

5. Jenkins is ready!


### A Final word

- While Jenkins is running:
    - All data is persisted in the location `C:\MNT\docker\jenkins\jenkins_home` 
    - If you need to restart Jenkins, type `docker compose up -d` at a command prompt in this project directory. If you've edited the `Dockerfile` or `plugins/plugins.txt`, use `docker compose up -d --build` instead so the image gets rebuilt first.

- If need access to the Jenkins container (to poke around the OS, jenkins file systems, etc.), type:
    
    ```
    docker compose exec jenkins /bin/bash
    ```


- To _end_ your Jenkins container experience, type: 

    ```
    docker compose down
    ```

### Manual step: enabling Content-Security-Policy enforcement

Manage Jenkins will show an admin warning recommending CSP enforcement be turned on (`jenkins.security.csp.impl.CspRecommendation`). This is a core Jenkins feature (since 2.539) with three ways to turn it on: the "Enforce Content Security Policy" checkbox under Manage Jenkins -> Security, Configuration-as-Code (`security: contentSecurityPolicy: enforce: true`, which would need the `configuration-as-code` plugin added), or the system property `jenkins.security.csp.CspHeader.headerName`.

This is left as a manual, one-time step rather than baked into an init script: the system-property route is the only one that's scriptable from `init-scripts/`, but setting it also permanently removes the UI checkbox afterward (admins can no longer toggle it from Manage Jenkins -> Security once set that way), which didn't seem worth trading away for a "sloppy"/local dev box. Since `jenkins_home` is a persistent volume, checking the box once via the UI survives container restarts/rebuilds just fine - no need to redo it each time.

_Note:_  don't confuse this with the older, narrower `hudson.model.DirectoryBrowserSupport.CSP` system property (settable via Groovy/`System.setProperty`) - that one only controls the CSP header for statically-served content (archived artifacts, workspace browser, HTML Publisher reports, etc.) and won't clear this particular admin warning.


