// Administrator bootstrap. Runs on EVERY Jenkins start, but only acts on a fresh home.
//
// Admin ID: JENKINS_ADMIN_ID (older name JENKINS_ADMIN_USERNAME also accepted), default "admin".
//  - Admin exists            -> nothing changes. Password and permissions are never reset.
//                               A WARNING is logged if that user does not have Administer.
//  - No users at all          -> create the admin and grant Overall/Administer (matrix auth).
//                               Password: JENKINS_ADMIN_PASSWORD, otherwise a random one written to
//                               $JENKINS_HOME/secrets/sloppy-initial-admin-password.
//  - Other users, no admin    -> WARNING only. Admins are never created or replaced silently
//                               (for example after JENKINS_ADMIN_ID was changed).
// Passwords are never printed.
import hudson.model.User
import hudson.security.GlobalMatrixAuthorizationStrategy
import hudson.security.HudsonPrivateSecurityRealm
import hudson.security.SecurityRealm
import jenkins.model.Jenkins
import org.jenkinsci.plugins.matrixauth.PermissionEntry

import java.nio.file.Files
import java.nio.file.StandardOpenOption
import java.nio.file.attribute.PosixFilePermissions
import java.security.SecureRandom

def jenkins = Jenkins.get()
def adminId = (System.getenv('JENKINS_ADMIN_ID') ?: System.getenv('JENKINS_ADMIN_USERNAME') ?: 'admin').trim()
def realm = jenkins.securityRealm

if (realm instanceof HudsonPrivateSecurityRealm) {
    def userIds = realm.allUsers*.id
    if (userIds.contains(adminId)) {
        def admin = User.getById(adminId, false)
        def isAdmin = false
        try {
            isAdmin = jenkins.getACL().hasPermission2(admin.impersonate2(), Jenkins.ADMINISTER)
        } catch (Exception e) {
            println("[sloppy] WARNING: could not check permissions for admin '${adminId}': ${e.class.simpleName}")
        }
        if (isAdmin) {
            println("[sloppy] Admin '${adminId}' already exists; security configuration left unchanged.")
        } else {
            println("[sloppy] WARNING: user '${adminId}' exists but does NOT have Overall/Administer. " +
                    'Security bootstrap is incomplete. Fix it in Manage Jenkins -> Security; this script will not change it.')
        }
        return
    }
    if (!userIds.isEmpty()) {
        println("[sloppy] WARNING: admin '${adminId}' not found, but ${userIds.size()} other user(s) exist. " +
                'No admin was created. If JENKINS_ADMIN_ID changed, create that user in Manage Jenkins -> Users.')
        return
    }
} else if (realm != SecurityRealm.NO_AUTHENTICATION) {
    println("[sloppy] Security realm is ${realm.class.simpleName}; not managed by Sloppy Jenkins, left unchanged.")
    return
}

// Fresh home: no users yet.
def password = System.getenv('JENKINS_ADMIN_PASSWORD')
def passwordFile = null
if (!password) {
    def alphabet = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789'
    def random = new SecureRandom()
    password = (1..24).collect { alphabet[random.nextInt(alphabet.length())] }.join()

    // Write the file before creating the account, so a write failure never leaves an unknown password.
    passwordFile = jenkins.rootDir.toPath().resolve('secrets').resolve('sloppy-initial-admin-password')
    Files.createDirectories(passwordFile.parent)
    Files.writeString(passwordFile, password + '\n', StandardOpenOption.CREATE, StandardOpenOption.TRUNCATE_EXISTING)
    try {
        Files.setPosixFilePermissions(passwordFile, PosixFilePermissions.fromString('rw-------'))
    } catch (UnsupportedOperationException ignored) {
        // Non-POSIX filesystem; the secrets directory is already restricted by Jenkins.
    }
}

def privateRealm = (realm instanceof HudsonPrivateSecurityRealm) ? realm : new HudsonPrivateSecurityRealm(false)
privateRealm.createAccount(adminId, password)
password = null
jenkins.securityRealm = privateRealm

def strategy = (jenkins.authorizationStrategy instanceof GlobalMatrixAuthorizationStrategy) ?
        jenkins.authorizationStrategy : new GlobalMatrixAuthorizationStrategy()
strategy.add(Jenkins.ADMINISTER, PermissionEntry.user(adminId))
jenkins.authorizationStrategy = strategy
jenkins.save()

if (passwordFile != null) {
    println("[sloppy] Created admin '${adminId}' with Overall/Administer. " +
            'Initial password written to $JENKINS_HOME/secrets/sloppy-initial-admin-password.')
} else {
    println("[sloppy] Created admin '${adminId}' with Overall/Administer. Password taken from JENKINS_ADMIN_PASSWORD.")
}
println('[sloppy] Security bootstrap complete.')
