#!/bin/sh
#
# update-java-ca-certs
#
# This scripts takes all certificates from Debian and places it into the
# CA-store of the current default java installation
#

#
# At first we try to detect the Java home directory
# http://rabexc.org/posts/certificates-not-working-java#comment-4099504075
#
#
# https://www.java-samples.com/showtutorial.php?tutorialid=210
# keytool -list -keystore $JAVA_HOME/jre/lib/security/cacerts
# keytool -import -alias myprivateroot -keystore $JAVA_HOME/jre/lib/security/cacerts  -file /var/jenkins_home/javajava/cacert.cer
# keytool -import -alias myprivateroot2 -keystore $JAVA_HOME/jre/lib/security/cacerts  -file /var/jenkins_home/javajava/cloud.cer
#
apt-get install ca-certificates-java
apt-get install ca-certificates

if [ ! -z "$JAVA_HOME" ]; then
    if [ -e "$JAVA_HOME/jre/lib/security/cacerts" ]; then
        CACERTS="$JAVA_HOME/jre/lib/security/cacerts"
    elif [ -e "$JAVA_HOME/lib/security/cacerts" ]; then
        CACERTS="$JAVA_HOME/lib/security/cacerts"
    fi
fi

if [ -z "$CACERTS" ]; then
    echo "Could not locate cacerts. Is JAVA_HOME set?"
    exit -1;
fi

cd /etc/ssl/certs
for file in *.pem; do
    echo "Importing $file..."
    openssl x509 -outform der -in "$file" -out /tmp/certificate.der
    keytool -import -alias "$file" -keystore $CACERTS \
            -file /tmp/certificate.der -deststorepass changeit -noprompt
done