This is the collection of plugins that will be consumed to be installed in Jenikns when setup via Dockerfile.

The thing I've discovered is IF you get a list of plugins from your Jenkins instance, this jenkins will be updated.
This means you may have to build stage up to the building of plugins.


All entries in plugins.txt are unpinned (no ":version" suffix) on purpose - that gets
jenkins-plugin-cli to resolve every plugin's current release together, as one consistent
dependency graph, at build time. That's handy for staying ahead of CVEs, but "latest" has broken
Jenkins on startup before due to plugin compatibility issues - and mixing pinned-old entries with
unpinned ones is worse, since it forces the resolver to satisfy old and new constraints at once
(that's what caused the AggregatePluginPrerequisitesNotMetException / ClassFormatError-style
failures during the 2026 CVE cleanup pass). If a plugin needs to be held back, pin it explicitly
rather than leaving some entries pinned and others not. Use the recommended loop below to lock
plugins.txt back down to a known-good pinned state if "latest" breaks something.

RECOMMENDED WORKFLOW:
1. Build/run with plugins.txt as-is (fully pinned, fully unpinned, or a deliberate mix).
2. If Jenkins fails to start or behaves incorrectly, fix it however's fastest - roll back the
   offending plugin via the UI Plugin Manager, or pin that one entry in plugins.txt and rebuild.
3. Once Jenkins is stable, run capture-installed-plugins.bat (in THIS folder) from the project
   root. It hits the running Jenkins instance's REST API and writes every installed plugin's
   exact shortName:version to plugins-installed-snapshot.txt.
4. Review that snapshot, then copy the versions you want into plugins.txt to re-pin them.

capture-installed-plugins.bat wraps capture-installed-plugins.ps1. By default it talks to
http://localhost:8787 using the admin/password credentials from init-scripts/setupusers.groovy
(same JENKINS_ADMIN_USERNAME/JENKINS_ADMIN_PASSWORD env var overrides apply); pass
-JenkinsUrl/-Username/-Password to override for a different instance.

ALSO RUN THIS BEFORE tearing down or upgrading the Jenkins instance - not just after a
build. jenkins_home (C:\MNT\docker\jenkins\jenkins_home) is where plugins actually live once
installed; if that volume gets deleted or a Jenkins core/plugin upgrade goes sideways, plugins.txt
(unpinned) alone won't tell you what was actually running. Run capture-installed-plugins.bat
first, keep plugins-installed-snapshot.txt around, and you've got the exact known-good versions
to pin back into plugins.txt and rebuild from scratch.

FALLBACK (if REST access is locked down): get the same list manually via
Manage Jenkins -> Script Console:

import jenkins.model.*;
Jenkins.instance.pluginManager.plugins.each{
  plugin ->
    println ("${plugin.getShortName()}:${plugin.getVersion()}")
}

Copy the short name:version contents into plugins.txt yourself.

IF you do run into dependency issues, here's how to fix them:

DISABLE the step: RUN jenkins-plugin-cli --verbose -f /usr/share/jenkins/ref/plugins.txt

Then bring the container up to that stage and start it:

docker compose up -d --build

NOTE: `docker compose` creates the C:\MNT\docker\jenkins\jenkins_home bind-mount folder
automatically if it doesn't already exist.

Docker will run the jenkins container "local_dev_jenkins" from the image we've previously
built (see compose.yaml - image "local_dev_jenkins_host").

We now need to get in to debug, so type:

docker compose exec jenkins /bin/bash

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




