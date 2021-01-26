This is the collection of plugins that will be consumed to be installed in Jenikns when setup via Dockerfile.

The thing I've discovered is IF you get a list of plugins from your Jenkins instance, this jenkins will be updated. 
This means you may have to build stage up to the building of plugins.




To get a list of plugins on your Jenkins instance:
1. Log into Jenkins.
2. Use the Scriptler plugin to create scripts to store on Jenkins

OR

Go to Manage Jenkins -> Script Console:

Plug in this script to get a list:

import jenkins.model.*;
Jenkins.instance.pluginManager.plugins.each{
  plugin -> 
    println ("${plugin.getShortName()}:${plugin.getVersion()}")
}

Copy the short name:version contents to a file called plugins.txt and put it in THIS folder.

IF you do run into dependency issues, here's how to fix them:

DISABLE the step: RUN jenkins-plugin-cli --verbose -f /usr/share/jenkins/ref/plugins.txt

If you have not ran the setup.bat, run it and type: restartjenkins

IF you don't want to, then follow the RUN WITH steps in dockerfile. OR you can run the following command if Docker image has been built up to the plugins stage:
docker run --name local_dev_jenkins -i -d -p 8787:8080 -p 50000:50000 -v C:\MNT\docker\jenkins\jenkins_home:/var/jenkins_home:rw local_dev_jenkins_host

NOTE: Make sure C:\MNT\docker\jenkins exist. Create it if not.


Docker will run the jenkins container "local_dev_jenkins" that is from our image we've previously created with dockerfile named "local_dev_jenkins_host". 

We now need to get in to debug, so type:

docker run -it local_dev_jenkins /bin/bash

NOTE: The default shell is /bin/sh. If you want to live a painful life, use /bin/sh.

run jenkins-plugin-cli --verbose -f /usr/share/jenkins/ref/plugins.txt

Run this until you hit a dependency problem. Should one appear you'll see an error that looks like this:

jackson2-api 2.12.1
structs 1.20
Skipping dependency workflow-step-api:2.23 and its sub-dependencies, because there is a higher version defined on the top level - workflow-step-api:2.23
io.jenkins.tools.pluginmanager.impl.PluginDependencyStrategyException: Plugin pipeline-model-api:1.7.2 depends on jackson2-api:2.12.1, but there is an older version defined on the top level - jackson2-api:2.12.0
        at io.jenkins.tools.pluginmanager.impl.PluginManager.resolveRecursiveDependencies(PluginManager.java:883)
        at io.jenkins.tools.pluginmanager.impl.PluginManager.findPluginsAndDependencies(PluginManager.java:493)
        at io.jenkins.tools.pluginmanager.impl.PluginManager.start(PluginManager.java:157)
        at io.jenkins.tools.pluginmanager.impl.PluginManager.start(PluginManager.java:117)
        at io.jenkins.tools.pluginmanager.cli.Main.main(Main.java:76)
Plugin pipeline-model-api:1.7.2 depends on jackson2-api:2.12.1, but there is an older version defined on the top level - jackson2-api:2.12.0

That LAST LINE is the fix: "pipeline-model-api:1.7.2 depends on jackson2-api:2.12.1"

The SECOND line is the problem: "Plugin pipeline-model-api:1.7.2 depends on jackson2-api:2.12.1, but there is an older version defined on the top level - jackson2-api:2.12.0"

So, in your plugins.txt file, modify the version from 2.12.0 to 2.12.1

Run run jenkins-plugin-cli --verbose -f /usr/share/jenkins/ref/plugins.txt

If more errors appear, rinse, wash, repeat. 




