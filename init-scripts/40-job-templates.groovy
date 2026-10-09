// Managed job templates. Runs on EVERY Jenkins start.
//
// Each <name>.xml in the image's job-templates directory becomes the job Templates/<name>.
// The repository owns these templates: if the XML in the image changed, or the template was edited
// in Jenkins, it is overwritten from the image. Only items inside the Templates folder are touched.
// Jobs that users copy from a template are independent and never modified.
//
// Templates ship disabled. To use one: New Item -> name -> "Copy from" Templates/<name>.
import com.cloudbees.hudson.plugins.folder.Folder
import jenkins.model.Jenkins

import javax.xml.transform.stream.StreamSource
import java.security.MessageDigest

def templateDir = new File(System.getenv('SLOPPY_TEMPLATE_DIR') ?: '/usr/share/jenkins/sloppy/job-templates')
if (!templateDir.isDirectory()) {
    println("[sloppy] WARNING: job template directory ${templateDir} not found; no templates managed.")
    return
}

def sha256 = { byte[] bytes -> MessageDigest.getInstance('SHA-256').digest(bytes).encodeHex().toString() }

def jenkins = Jenkins.get()
def folder = jenkins.getItem('Templates')
if (folder == null) {
    folder = jenkins.createProject(Folder, 'Templates')
    folder.description = 'Managed by Sloppy Jenkins (job-templates/ in the repository). ' +
            'Do not edit these jobs; copy one with New Item -> "Copy from" and configure the copy.'
    folder.save()
    println('[sloppy] Created folder Templates.')
} else if (!(folder instanceof Folder)) {
    println("[sloppy] WARNING: 'Templates' exists but is not a folder (${folder.class.simpleName}); templates not managed.")
    return
}

templateDir.listFiles().findAll { it.isFile() && it.name.endsWith('.xml') }.sort { it.name }.each { file ->
    def name = file.name[0..-5]
    def templateBytes = file.bytes
    def templateHash = sha256(templateBytes)
    def item = folder.getItem(name)

    if (item != null) {
        def marker = new File(item.rootDir, '.sloppy-template')
        def configHash = sha256(item.configFile.file.bytes)
        if (marker.isFile() && marker.text.trim() == "${templateHash} ${configHash}") {
            println("[sloppy] Template Templates/${name} is up to date.")
            return
        }
        item.updateByXml(new StreamSource(new ByteArrayInputStream(templateBytes)))
        println("[sloppy] Template Templates/${name} refreshed from the image.")
    } else {
        item = folder.createProjectFromXML(name, new ByteArrayInputStream(templateBytes))
        println("[sloppy] Template Templates/${name} created.")
    }

    // Record what was applied, so unchanged templates are skipped on the next start.
    def written = folder.getItem(name)
    new File(written.rootDir, '.sloppy-template').text = "${templateHash} ${sha256(written.configFile.file.bytes)}\n"
}
