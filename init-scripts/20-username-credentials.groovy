// Username/password credentials from .env. Runs on EVERY Jenkins start; creates only what is missing.
//
// Define one numbered set per credential in .env (values are taken literally, no quotes):
//   SLOPPY_CRED_1_ID=gitlab-repo-token
//   SLOPPY_CRED_1_USER=my-gitlab-user
//   SLOPPY_CRED_1_PASSWORD=the-password-or-token
//   SLOPPY_CRED_1_DESCRIPTION=GitLab read-only token     (optional)
//   SLOPPY_CRED_2_ID=...                                  (numbers may have gaps: 1, 2, 10)
//
// Processing order for each set (numeric order):
//  1. All of ID, USER, PASSWORD, DESCRIPTION empty or absent -> skipped silently.
//  2. ID missing or invalid (letters, digits, _ . - only)      -> WARNING, skipped.
//  3. A credential with that ID already exists                 -> left unchanged (never overwritten).
//     So after the first start you may delete the set's PASSWORD line from .env without warnings.
//  4. USER or PASSWORD missing                                 -> WARNING naming the variables, skipped.
//  5. Otherwise a global "Username with password" credential is created.
// USER, PASSWORD and DESCRIPTION are used exactly as written (no trimming); only the ID is trimmed.
// Values are never printed, only IDs and variable names. Nothing is printed when no sets are defined.
import com.cloudbees.plugins.credentials.CredentialsScope
import com.cloudbees.plugins.credentials.SystemCredentialsProvider
import com.cloudbees.plugins.credentials.common.IdCredentials
import com.cloudbees.plugins.credentials.domains.Domain
import com.cloudbees.plugins.credentials.impl.UsernamePasswordCredentialsImpl

def env = System.getenv()
// A set exists if ANY of its variables is present, so a set missing its ID is still reported.
// The number is kept exactly as written (so SLOPPY_CRED_01_* reads the "01" variables) and only sorted
// as a BigInteger, which never overflows: no .env value can make this script throw here.
def numbers = env.keySet()
        .collect { name -> (name =~ /^SLOPPY_CRED_(\d+)_(ID|USER|PASSWORD|DESCRIPTION)$/) }
        .findAll { it.matches() }
        .collect { it.group(1) }
        .unique()
        .sort { a, b -> (new BigInteger(a) <=> new BigInteger(b)) ?: (a <=> b) }

if (numbers.isEmpty()) {
    return
}

// Raw value, or null when the variable is absent or empty. No trimming: values are literal.
def raw = { String name -> def v = env[name]; (v == null || v.isEmpty()) ? null : v }
def store = SystemCredentialsProvider.getInstance().getStore()
def domain = Domain.global()
def existingIds = store.getCredentials(domain).findAll { it instanceof IdCredentials }*.id as Set

numbers.each { n ->
    def prefix = "SLOPPY_CRED_${n}_"
    def id = raw(prefix + 'ID')?.trim() ?: null
    def user = raw(prefix + 'USER')
    def password = raw(prefix + 'PASSWORD')
    def description = raw(prefix + 'DESCRIPTION')

    if (id == null && user == null && password == null && description == null) {
        return   // completely empty set, e.g. copied from .env.example: nothing to do, nothing to say
    }
    if (id == null) {
        println("[sloppy] WARNING: credential set ${n} skipped: missing ${prefix}ID.")
        return
    }
    if (!(id ==~ /[A-Za-z0-9_.\-]+/)) {
        println("[sloppy] WARNING: credential set ${n} skipped: ${prefix}ID may only contain letters, digits, '_', '.' and '-'.")
        return
    }
    if (existingIds.contains(id)) {
        println("[sloppy] Credential '${id}' already exists; left unchanged.")
        return
    }
    def missing = []
    if (user == null) missing << prefix + 'USER'
    if (password == null) missing << prefix + 'PASSWORD'
    if (missing) {
        println("[sloppy] WARNING: credential set ${n} ('${id}') skipped: missing ${missing.join(', ')}.")
        return
    }

    // try/catch: an error here must not stop the later startup scripts (Jenkins skips them all if one
    // script throws). Only the error type is printed, never its message, which could echo a value.
    try {
        def credential = new UsernamePasswordCredentialsImpl(CredentialsScope.GLOBAL, id,
                description ?: 'Created by Sloppy Jenkins from .env', user, password)
        if (store.addCredentials(domain, credential)) {
            existingIds << id
            println("[sloppy] Created credential '${id}' (set ${n}).")
        } else {
            println("[sloppy] WARNING: could not create credential '${id}' (set ${n}).")
        }
    } catch (Exception e) {
        println("[sloppy] WARNING: could not create credential '${id}' (set ${n}): ${e.class.simpleName}.")
    }
}
