#!/bin/bash

# This script will detect if there is a Wedge power driver
# and tell you the ip address of the Wedge BMC

# The LLA of OpenBMC and default username password
SWLLA="fe80::ff:fe00:2" # needed to find the DEV for internal BMC network
BMCLLA="fe80::1" # The BMC's LLA
SSHUSER="root" # Default username
SSHPASS="0penBmc" # Default password

Error(){
        echo "ERROR: $1"
        exit 1
}

Usage(){
        cat <<EOF
Usage: ${0##*/} [ options ]

   node enlistment into the MAAS server

   options:
      -c | --check            check if this is a wedge
      -g | --get-credentials  obtain the credentials for the wedge

   Example:
    - ${0##*/} --check

EOF
}

bad_Usage() { Usage 1>&2; [ $# -eq 0 ] || Error "$@"; }

short_opts="hs:c:g:"
long_opts="help,check,get-credentials,"
getopt_out=$(getopt --name "${0##*/}" \
        --options "${short_opts}" --long "${long_opts}" -- "$@") &&
        eval set -- "${getopt_out}" ||
        bad_Usage

if [ -z "$(which sshpass)" ]
then
        Error "please apt-get install sshpass"
fi

# Obtain the 'net' device connected to the BMC.
DEV="$(ip -o a show to "${SWLLA}" | awk '// { print $2 }')" || Error "Unable to detect the 'wedge' net device connected to the BMC."

wedge_autodetect(){
    # Verify that this is an openBMC.
    if ! curl -s 'http://['"${BMCLLA}"%"${DEV}"']:8080/api' | grep -qs 'Wedge RESTful API Entry'; then
        Error "Unable to detect a 'wedge' BMC."
    fi
    echo "wedge"
}

wedge_discover(){
    # Obtain the IP address of the BMC by logging into it using the default values (we cannot auto-discover
    # non-default values).
    IP="$(sshpass -p "${SSHPASS}" ssh -o StrictHostKeyChecking=no "${SSHUSER}"@"${BMCLLA}"%"${DEV}" \
        'ip -o -4 addr show | awk "{ if(NR>1)print \$4 "} | cut -d/ -f1')" || Error "Unable to obtain the 'wedge' BMC IP address."
    # If we were able to optain the IP address, then we can simply return the credentials.
    echo "$SSHUSER,$SSHPASS,$IP,"
}

while [ $# -ne 0 ]; do
        cur="${1}"; next="${2}";
        case "$cur" in
                -h|--help) Usage; exit 0;;
                -c|--check) wedge_autodetect; exit 0;;
                -g|--get-credentials) wedge_discover; exit 0;;
                --) shift; break;;
        esac
        shift;
done
Usage

