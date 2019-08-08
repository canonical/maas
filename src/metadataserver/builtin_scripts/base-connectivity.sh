function test_url() {
    INTERFACE=$1
    URL=$2
    cmd_failed=0
    for i in $(echo $URL | sed 's/,/ /g'); do
        if $(echo $i | egrep -q '^icmp://') || $(echo $i | egrep -q -v '://'); then
            if [ $(echo $i | egrep -q '://') ]; then
                # ping doesn't accept a protocol.
                i=$(echo $i | awk -F '://' '{print $2}')
            fi
            CMD="ping -c 10"
            if [ -n "$INTERFACE" ]; then
                CMD="$CMD -I $INTERFACE"
            fi
        else
            CMD="curl -ILSsv -A maas_internet_connectivity_test"
            if [ -n "$INTERFACE" ]; then
                CMD="$CMD --interface $INTERFACE"
            fi
        fi
        CMD="$CMD $i"
        echo "Running command: $CMD"
        echo
        eval $CMD
        cmd_failed=$((cmd_failed||$?))
        echo
        echo
    done
    return $cmd_failed
}


function test_bond() {
    BOND=$1
    URL=$2
    INTERFACE=${3:-$BOND}
    slaves_path="/sys/devices/virtual/net/$BOND/bonding/slaves"
    slaves=$(cat $slaves_path)
    cmd_failed=0
    for test_slave in $(echo $slaves); do
        # Remove all other interfaces from the bond
        for remove_slave in $(echo $slaves | grep -v $test_slave); do
            echo "-$remove_slave" > $slaves_path
        done
        echo "Testing $INTERFACE with only $test_slave attached..."
        test_url "$INTERFACE" "$URL"
        cmd_failed=$((cmd_failed||$?))
        # Add back all slaves incase the last device was broken and only
        # the bond was configured.
        for add_slave in $(echo $slaves | grep -v $test_slave); do
            echo "+$add_slave" > $slaves_path
        done
    done
    return $cmd_failed
}


function test_interface() {
    INTERFACE=$1
    URL=$2
    if [ -n "$INTERFACE" ] && [ -d /sys/class/net/$INTERFACE/bridge ]; then
        cmd_failed=0
        found_bond=0
        for i in /sys/devices/virtual/net/$INTERFACE/lower_*/bonding; do
            found_bond=1
            bond=$(basename $(dirname $i) | cut -d '_' -f2)
            echo "$INTERFACE is backed by bond $bond, each slave will be tested individually..."
            echo
            test_bond "$bond" "$URL" "$INTERFACE"
            cmd_failed=$((cmd_failed||$?))
        done
        if [ $found_bond -eq 0 ]; then
            test_url "$INTERFACE" "$URL"
            cmd_failed=$?
        fi
        exit $cmd_failed
    elif [ -n "$INTERFACE" ] && $(cat /sys/class/net/bonding_masters 2>/dev/null | grep -q "$INTERFACE"); then
        echo "$INTERFACE is a bond, each slave will be tested individually..."
        echo
        test_bond "$INTERFACE" "$URL"
        exit $?
    else
        test_url "$INTERFACE" "$URL"
        exit $?
    fi
}
