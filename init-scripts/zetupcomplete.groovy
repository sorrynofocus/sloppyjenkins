import jenkins.model.*;
import hudson.util.*;
import jenkins.install.*;

jsl = Jenkins.getInstance();
//uw = jsl.getInjector().getInstance(UpgradeWizard.class);
//uw.setCurrentLevel(new VersionNumber("2.0"));
jsl.setInstallState(InstallState.INITIAL_SETUP_COMPLETED);