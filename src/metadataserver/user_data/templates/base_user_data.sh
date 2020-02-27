#!/bin/bash
#
# This script carries inside it multiple files.  When executed, it creates
# the files into a temporary directory and uses them to execute commands
# which gather data about the running machine or perform actions.
#

#### script setup ######
export TEMP_D
TEMP_D=$(mktemp -d "${TMPDIR:-/tmp}/${0##*/}.XXXXXX")
export BIN_D="${TEMP_D}/bin"
export PATH="$BIN_D:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

mkdir -p "$BIN_D"

# Ensure that invocations of apt-get are not interactive by default,
# here and in all subprocesses.
export DEBIAN_FRONTEND=noninteractive

### some utility functions ####
add_bin() {
    cat > "${BIN_D}/$1"
    chmod "${2:-755}" "${BIN_D}/$1"
}

fail() {
    [ -z "$CRED_CFG" ] || signal FAILED "$1"
    echo "FAILED: $1" 1>&2;
    exit 1
}

find_creds_cfg() {
    local file="" found=""

    # If the config location is set in environment variable, trust it.
    [ -n "${COMMISSIONING_CREDENTIALS_URL}" ] &&
      _RET="${COMMISSIONING_CREDENTIALS_URL}" && return

    # Go looking for local files written by cloud-init.
    for file in /etc/cloud/cloud.cfg.d/*cmdline*.cfg; do
        [ -f "$file" ] && _RET="$file" && return
    done

    local opt="" cmdline=""
    if [ -r /proc/cmdline ]; then
        cmdline=$(< /proc/cmdline)
        # Search through /proc/cmdline arguments:
        # cloud-config-url trumps url=
        for opt in $cmdline; do
            case "$opt" in
                url=*)
                    found=${opt#url=};;
                cloud-config-url=*)
                    _RET="${opt#*=}"
                    return 0;;
            esac
        done
        [ -n "$found" ] && _RET="$found" && return 0
    fi
    return 1
}

# Do everything needed to be able to use maas_api_helper or any script which
# imports it.
prep_maas_api_helper() {
    local creds=""

    find_creds_cfg || fail "Failed to find credential config"
    creds="$_RET"

    # Get remote credentials into a local file.
    case "$creds" in
        http://*|https://*)
            wget "$creds" -O "${TEMP_D}/my.creds" ||
              fail "failed to get credentials from $creds"
            creds="${TEMP_D}/my.creds"
            ;;
    esac

    # Use global name read by signal().
    export CRED_CFG="$creds"
}

####  IPMI setup  ######
# If IPMI network settings have been configured statically, you can
# make them DHCP. If 'true', the IPMI network source will be changed
# to DHCP.
# IPMI_AUTODETECT_ARGS="--dhcp-if-static"

# In certain hardware, the parameters for the ipmi_si kernel module
# might need to be specified. If you wish to send parameters, uncomment
# the following line.
#IPMI_SI_PARAMS="type=kcs ports=0xca2"

# Load the IPMI kernel modules for enlistment and commissioning
load_ipmi_modules() {
    modprobe ipmi_msghandler
    modprobe ipmi_devintf
    modprobe ipmi_si "${IPMI_SI_PARAMS}"
    modprobe ipmi_ssif
    udevadm settle
}

get_power_type() {
    local power_type
    power_type=$(maas-ipmi-autodetect-tool)
    if [ -z "$power_type" ]; then
        power_type=$(maas-wedge-autodetect --check) || power_type=""
    fi
    echo "$power_type"
}

# Invoke the "signal()" API call to report progress.
# Usage: signal <status> <message>
signal() {
    maas-signal "--config=${CRED_CFG}" "$@"
}
