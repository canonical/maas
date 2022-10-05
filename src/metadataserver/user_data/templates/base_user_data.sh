#!/bin/bash
#
# This script carries inside it multiple files.  When executed, it creates
# the files into a temporary directory and uses them to execute commands
# which gather data about the running machine or perform actions.
#

#### script setup ######
export TEMP_D
TMPDIR=${MAAS_DATA:-/var/lib/maas}
TEMP_D=$(mktemp -d "${TMPDIR}/${0##*/}.XXXXXX")
export BIN_D="${TEMP_D}/bin"
export PATH="$BIN_D:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

trap "rm -rf $TEMP_D" EXIT
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

# Invoke the "signal()" API call to report progress.
# Usage: signal <status> <message>
signal() {
    maas-signal "--config=${CRED_CFG}" "$@"
}
