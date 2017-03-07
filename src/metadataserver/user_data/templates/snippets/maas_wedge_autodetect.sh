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
      -e | --get-enlist-creds obtain the credentials for the wedge for enlistment
      -h | --help             display usage

   Example:
    - ${0##*/} --check

EOF
}

bad_Usage() { Usage 1>&2; [ $# -eq 0 ] || Error "$@"; }

short_opts="hcge"
long_opts="help,check,get-credentials,get-enlist-creds"
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

# Get dmidecode information to find out if this is a switch
SM="$(dmidecode -s system-manufacturer)"
SPN="$(dmidecode -s system-product-name)"
BPN="$(dmidecode -s baseboard-product-name)"

detect_known_switch(){
    # This is based of https://github.com/lool/sonic-snap/blob/master/common/id-switch
    # try System Information > Manufacturer first
    case "$SM" in
        "Intel")
            case "$SPN" in
                "EPGSVR")
                    manufacturer=accton
                    ;;
                *)
                    Error "Unable to detect switch"
                    ;;
            esac
            ;;
        "Joytech")
            case "$SPN" in
                "Wedge-AC-F 20-001329")
                    manufacturer=accton
                    ;;
                *)
                    Error "Unable to detect switch"
                    ;;
            esac
            ;;
        "To be filled by O.E.M.")
            case "$BPN" in
                "PCOM-B632VG-ECC-FB-ACCTON-D")
                    manufacturer=accton
                    ;;
                *)
                    Error "Unable to detect switch"
                    ;;
            esac
            ;;
        *)
            Error "Unable to detect switch"
            ;;
    esac
    # next look at System Information > Product Name
    case "$manufacturer-$SPN" in
        "accton-EPGSVR")
            model=wedge40
            ;;
        "accton-Wedge-AC-F 20-001329")
            model=wedge40
            ;;
        "accton-To be filled by O.E.M.")
            case "$BPN" in
                "PCOM-B632VG-ECC-FB-ACCTON-D")
                    model=wedge100
                    ;;
                *)
                    Error "Unable to detect switch model"
                    ;;
            esac
            ;;
        *)
            Error "Unable to detect switch model"
            ;;
    esac
    echo "$model"
}

wedge_autodetect(){
    # First detect this is a known switch
    model=$(detect_known_switch) || Error "Unable to detect switch model"
    # Second, lets verify if this is a known endpoint
    # First try to hit the API. This would work on Wedge 100.
    if curl -s 'http://['"${BMCLLA}"%"${DEV}"']:8080/api' | grep -qs 'Wedge RESTful API Entry'; then
        echo "wedge"
    # If the above failed, try to hit the SSH. This would work on Wedge 40
    elif [ ! -z "$(sshpass -p "${SSHPASS}" ssh -o StrictHostKeyChecking=no "${SSHUSER}"@"${BMCLLA}"%"${DEV}" 'ip -o -4 addr show | awk "{ if(NR>1)print \$4 "} | cut -d/ -f1')" ]; then
        echo "wedge"
    else
        Error "Unable to detect the BMC for a "$model" switch"
    fi
}

wedge_discover(){
    # Obtain the IP address of the BMC by logging into it using the default values (we cannot auto-discover
    # non-default values).
    IP="$(sshpass -p "${SSHPASS}" ssh -o StrictHostKeyChecking=no "${SSHUSER}"@"${BMCLLA}"%"${DEV}" \
        'ip -o -4 addr show | awk "{ if(NR>1)print \$4 "} | cut -d/ -f1')" || Error "Unable to obtain the 'wedge' BMC IP address."
    # If we were able to optain the IP address, then we can simply return the credentials.
    echo "$SSHUSER,$SSHPASS,$IP,"
}


wedge_discover_json(){
    # Obtain the IP address of the BMC by logging into it using the default values (we cannot auto-discover
    # non-default values).
    IP="$(sshpass -p "${SSHPASS}" ssh -o StrictHostKeyChecking=no "${SSHUSER}"@"${BMCLLA}"%"${DEV}" \
        'ip -o -4 addr show | awk "{ if(NR>1)print \$4 "} | cut -d/ -f1')" || Error "Unable to obtain the 'wedge' BMC IP address."
    # If we were able to optain the IP address, then we can simply return the credentials.
    echo -e "{\"power_user\":\""$SSHUSER"\", \"power_pass\":\""$SSHPASS"\",\"power_address\":\""$IP"\"}"
}

while [ $# -ne 0 ]; do
        cur="${1}"; next="${2}";
        case "$cur" in
                -h|--help) Usage; exit 0;;
                -c|--check) wedge_autodetect; exit 0;;
                -g|--get-credentials) wedge_discover; exit 0;;
                -e|--get-enlist-creds) wedge_discover_json; exit 0;;
                --) shift; break;;
        esac
        shift;
done
Usage

