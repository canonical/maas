#!/bin/bash -e
#
# Helper script to install and configur a test LDAP server.


HOSTNAME="$(hostname)"
ADMIN_PASS="pass"

CERT_NAME="${1:-$HOSTNAME}"
CERT_DIR="$PWD/certs"

install_ldap() {
    apt update
    apt install -y debconf-utils
        debconf-set-selections <<EOF
slapd slapd/password1 password $ADMIN_PASS
slapd slapd/internal/adminpw password $ADMIN_PASS
slapd slapd/internal/generated_adminpw password $ADMIN_PASS
slapd slapd/password2 password $ADMIN_PASS
slapd slapd/purge_database boolean true
slapd slapd/domain string example.com
slapd slapd/invalid_config boolean true
slapd slapd/move_old_database boolean true
slapd slapd/backend select MDB
slapd shared/organization string myorg
slapd slapd/dump_database select when needed
slapd slapd/unsafe_selfwrite_acl note
slapd slapd/dump_database_destdir string /var/backups/slapd-VERSION
slapd slapd/ppolicy_schema_needs_update select abort installation
slapd slapd/no_configuration boolean false
slapd slapd/password_mismatch note
EOF
    apt install -y slapd ldap-utils
}

make_certs() {
    local name="$1"
    local easyrsa_dir="$PWD/easy-rsa"
    local easyrsa="$easyrsa_dir/easyrsa3/easyrsa"
    local pkidir="$PWD/pki"

    if [ ! -d "$easyrsa_dir" ]; then
        git clone https://github.com/OpenVPN/easy-rsa.git
    fi

    [ ! -d "$CERT_DIR" ] || return

    # create certs
    "$easyrsa" init-pki
    "$easyrsa" build-ca nopass
    "$easyrsa" gen-req "$name" nopass
    "$easyrsa" sign-req server "$name"

    # copy certs in the target dir
    mkdir -p "$CERT_DIR"
    cp "$pkidir/ca.crt" "$pkidir/issued/$name.crt" \
       "$pkidir/private/$name.key" "$CERT_DIR"
}

install_certs() {
    local targetdir="/etc/ldap/certs"
    cp -a "$CERT_DIR" "$targetdir"
    chown -R openldap:openldap "$targetdir"
    chmod 600 "$targetdir/$CERT_NAME.key"
}

ldif_tls() {
    cat <<EOF
dn: cn=config
add: olcTLSCACertificateFile
olcTLSCACertificateFile: /etc/ldap/certs/ca.crt
-
add: olcTLSCertificateFile
olcTLSCertificateFile: /etc/ldap/certs/$CERT_NAME.crt
-
add: olcTLSCertificateKeyFile
olcTLSCertificateKeyFile: /etc/ldap/certs/$CERT_NAME.key
EOF
}

ldif_users() {
    cat <<EOF
dn: ou=users,dc=example,dc=com
objectClass: organizationalUnit
ou: myorg

dn: uid=user1,ou=users,dc=example,dc=com
objectClass: account
objectClass: simpleSecurityObject
uid: user1
description: User One
userPassword: pass1

dn: uid=user2,ou=users,dc=example,dc=com
objectClass: account
objectClass: simpleSecurityObject
uid: user2
description: User Two
userPassword: pass2

dn: uid=user3,ou=users,dc=example,dc=com
objectClass: account
objectClass: simpleSecurityObject
uid: user3
description: User Three
userPassword: pass3

dn: cn=group1,ou=users,dc=example,dc=com
objectClass: groupOfNames
description: Group One
member: uid=user1,ou=users,dc=example,dc=com
member: uid=user2,ou=users,dc=example,dc=com

dn: cn=group2,ou=users,dc=example,dc=com
objectClass: groupOfNames
description: Group Two
member: uid=user2,ou=users,dc=example,dc=com

dn: cn=group3,ou=users,dc=example,dc=com
objectClass: groupOfNames
description: Group Three
member: uid=user3,ou=users,dc=example,dc=com
EOF
}

setup_ldap() {
    service slapd restart
    ldif_tls | ldapmodify -H ldapi:// -Y EXTERNAL
    ldif_users | ldapadd -D cn=admin,dc=example,dc=com -w $ADMIN_PASS
}

test_ldap() {
    echo "Testing LDAP access:"
    ldapwhoami -H ldap:// -D cn=admin,dc=example,dc=com -w $ADMIN_PASS
    ldapwhoami -H ldap:// -D uid=user1,ou=users,dc=example,dc=com -w pass1
}

install_ldap
make_certs "$CERT_NAME"
install_certs
setup_ldap
test_ldap
