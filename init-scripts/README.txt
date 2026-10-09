This area contains the groovy initialisation scripts that Jenkins runs.

How they run
------------
- The Dockerfile copies init-scripts/*.groovy into the image (/usr/share/jenkins/ref/init.groovy.d).
- On every container start the image deletes $JENKINS_HOME/init.groovy.d and copies these scripts
  back in (PRE_CLEAR_INIT_GROOVY_D=true in the Dockerfile). The repository owns that folder:
    * To retire a script, delete it here and run: docker compose up -d --build
    * A script placed by hand in C:\MNT\docker\jenkins\jenkins_home\init.groovy.d is NOT supported;
      it is deleted on the next start. Put custom scripts here and rebuild instead.
    * To turn this off, remove the PRE_CLEAR_INIT_GROOVY_D line from the Dockerfile. Setting it to
      "false" does NOT work: the image clears the folder whenever the variable has any value.
- Jenkins runs EVERY script in init.groovy.d on EVERY start, in file-name order. Marking setup as
  complete only hides the setup wizard; it does not stop these scripts. So every script here is
  idempotent: it checks first and only creates what is missing.
- Removing a script does not undo what it created (users, nodes, credentials, jobs stay in
  jenkins_home). Remove those in the Jenkins UI if you no longer want them.

Scripts
-------
00-controller.groovy      Controller has 0 executors, CSRF protection on, setup wizard marked complete,
                          Jenkins URL set only when empty (or from SLOPPY_JENKINS_URL).
10-security.groovy        Fresh home only: creates the admin account (JENKINS_ADMIN_ID / JENKINS_ADMIN_PASSWORD
                          from .env, or a random password written to
                          jenkins_home\secrets\sloppy-initial-admin-password) with Overall/Administer.
                          An existing admin is never changed; a WARNING is logged if it lacks Administer.
20-username-credentials.groovy
                          Creates "Username with password" credentials from numbered .env sets
                          (SLOPPY_CRED_<n>_ID / _USER / _PASSWORD / optional _DESCRIPTION), only for IDs
                          that do not exist yet. Existing credentials are never overwritten (so a PASSWORD
                          line can be removed after the first start). Values are used exactly as written.
                          Incomplete sets and invalid IDs are skipped with a WARNING; empty sets are silent.
                          Values are never printed.
30-windows-agent.groovy   Creates the inbound Windows node windows_build_agent (C:\Jenkins, label windows-label,
                          1 executor, exclusive) when it is missing. Existing nodes are never changed.
31-ssh-agent.groovy       Optional SSH-launched node, only when SLOPPY_SSH_AGENT_HOST is set (silent otherwise).
                          Created when missing, never changed afterwards. Logs in with the "Username with
                          password" credential SLOPPY_SSH_AGENT_CRED_ID (default jenkins_agent_credentials),
                          which a SLOPPY_CRED_<n> set can create (20- runs first); warns if it does not exist.
                          Host keys must be trusted once in the UI. Default label windows-label is shared with
                          the inbound node, so set SLOPPY_SSH_AGENT_LABELS if jobs must stay on one node.
40-job-templates.groovy   Creates/refreshes Templates/* from job-templates/*.xml. Only the Templates folder is touched.

Optional scripts (do nothing until configured in .env)
------------------------------------------------------
20-username-credentials.groovy and 31-ssh-agent.groovy are always in the image but stay silent and change
nothing unless their .env variables are set. See .env.example.
