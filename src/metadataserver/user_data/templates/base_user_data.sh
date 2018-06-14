#!/bin/bash
#
# This script carries inside it multiple files.  When executed, it creates
# the files into a temporary directory and uses them to execute commands
# which gather data about the running machine or perform actions.
#

#### script setup ######
export TEMP_D=$(mktemp -d "${TMPDIR:-/tmp}/${0##*/}.XXXXXX")
export BIN_D="${TEMP_D}/bin"
export PATH="$BIN_D:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

mkdir -p "$BIN_D"

#### FIXME: Remove work around when the issue is fixed in resolvconf ###
#
# LP: #1711760
# Work around issue where resolv.conf is not set on the  ephemeral environment
#
# First check if a nameserver is set in resolv.conf
if ! grep -qs nameserver /etc/resolv.conf; then
    # If it is not, obtain the MAC address of the PXE boot interface
    bootif=$(cat /proc/cmdline | grep -o -E 'BOOTIF=01-([[:xdigit:]]{1,2}-){5}[[:xdigit:]]{1,2}')
    mac_address=$(echo $bootif | awk -F'=01-' '{print $NF}' | sed -r 's/-/:/g')

    # Search for the NIC name of the PXE boot interface
    for nic in /sys/class/net/*; do
        nic_mac=$(cat $nic/address)
        if [ "$nic_mac" == "$mac_address" ]; then
            # Get the interface name and ask dhclient to refresh the lease
            interface=$(echo $nic | cut -d'/' -f5)
            dhclient $interface || true
            break
        fi
    done
fi

######################

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
    local config="" file="" found=""

    # If the config location is set in environment variable, trust it.
    [ -n "${COMMISSIONING_CREDENTIALS_URL}" ] &&
      _RET="${COMMISSIONING_CREDENTIALS_URL}" && return

    # Go looking for local files written by cloud-init.
    for file in /etc/cloud/cloud.cfg.d/*cmdline*.cfg; do
        [ -f "$file" ] && _RET="$file" && return
    done

    local opt="" cmdline=""
    if [ -f /proc/cmdline ] && read cmdline < /proc/cmdline; then
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
              fail "failed to get credentials from $cred_cfg"
            creds="${TEMP_D}/my.creds"
            ;;
    esac

    # Use global name read by signal().
    export CRED_CFG="$creds"
}

# Invoke the "signal()" API call to report progress.
# Usage: signal <status> <message>
signal() {
    maas-signal "--config=${CRED_CFG}" "$@"
}
