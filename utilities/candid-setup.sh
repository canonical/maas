#!/bin/bash -e
#
# Helper script to install and configur a test LDAP server.

FQDN="$(hostname -f)"
HOSTNAME="$(hostname)"
ADMIN_PASS="pass"

CERT_NAME="${1:-$HOSTNAME}"
CERT_DIR="$PWD/certs"

install_candid() {
    echo "Installing candid & postgresql"
    apt-get install candid postgresql -y
}

create_candid_database() {
    echo "Creating candid PostgreSQL user & database"
    sudo -u postgres bash -c "psql -c \"CREATE USER candid WITH PASSWORD '$ADMIN_PASS';\""
    su postgres -c "createdb candid -O candid"
}

create_candid_admin_creds() {
    echo "Creating admin.agent and service.keys"
    export CANDID_URL="https://$FQDN:8081"
    candid put-agent -f admin.agent --admin
    candid put-agent -f service.keys --admin
}

create_candid_config() {
    echo "Creating candid config.yaml"
    SERVICE_PUBLIC_KEY=$(cat service.keys  | grep public | cut -d"\"" -f 4)
    SERVICE_PRIVATE_KEY=$(cat service.keys  | grep private | cut -d"\"" -f 4)
    AGENT_PUBLIC_KEY=$(cat admin.agent  | grep public | cut -d"\"" -f 4)
    KEY_PEM=$(cat "$CERT_DIR"/"$HOSTNAME".key | sed -E -e 's/^/ /')
    CA_PEM=$(cat "$CERT_DIR"/ca.crt | sed -E -e 's/^/ /')
    CERT_PEM=$(sed -n '/^---*/,/*/{p}' "$CERT_DIR/"$HOSTNAME".crt" | sed -E -e 's/^/ /')

    cat << EOF > config.yaml
listen-address: :8081
location: 'https://$FQDN:8081'
storage:
  type: postgres
  connection-string: dbname=candid user=candid password=$ADMIN_PASS
private-key: $SERVICE_PRIVATE_KEY
public-key: $SERVICE_PUBLIC_KEY
access-log: access.log
private-addr: localhost
admin-agent-public-key: $AGENT_PUBLIC_KEY
resource-path: /usr/share/candid
tls-cert: |
$CERT_PEM
$CA_PEM
tls-key: |
$KEY_PEM
identity-providers:
 - type: ldap
   name: ldap
   domain: ldap
   url: ldap://$FQDN/dc=example,dc=com
   dn: cn=admin,dc=example,dc=com
   password: $ADMIN_PASS
   user-query-filter: (objectClass=account)
   user-query-attrs:
     id: uid
     email: mail
     display-name: displayName
   group-query-filter: (&(objectClass=groupOfNames)(member={{.User}}))
EOF
}

restart_candid() {
    echo "Copying configuration to /etc/candid/ & restarting"
    sudo cp config.yaml /etc/candid/
    sudo systemctl restart candid.service
}

create_maas_credentials() {
    echo "Including certificates and creating MAAS credentials"
    export CANDID_URL="https://$FQDN:8081"
    ## TODO: This should live with ldap setup.
    mkdir -p /usr/share/ca-certificates/candid
    cp $CERT_DIR/*.crt /usr/share/ca-certificates/candid/
    sudo dpkg-reconfigure ca-certificates

    candid put-agent -a admin.agent -f maas.agent grouplist@candid
}

install_candid
create_candid_database
create_candid_admin_creds
create_candid_config
restart_candid
create_maas_credentials
