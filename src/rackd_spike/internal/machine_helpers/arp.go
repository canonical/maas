package machinehelpers

import (
	"context"
	"errors"
	"net"
	"os/exec"
	"strings"
)

var (
	ErrIPNotFound = errors.New("ip not found for given mac address")
)

func FindIPByArp(ctx context.Context, mac net.HardwareAddr) (net.IP, error) {
	cmd := exec.CommandContext(ctx, "arp", "-n")

	out, err := cmd.CombinedOutput()
	if err != nil {
		return nil, err
	}

	for _, line := range strings.Split(string(out), "\n") {
		columns := strings.Split(line, "  ")
		var strippedColumns []string
		for _, column := range columns {
			column = strings.TrimSpace(column)
			if column == "" {
				continue
			}
			strippedColumns = append(strippedColumns, column)
		}
		columns = strippedColumns
		if len(columns) == 5 && strings.ToLower(columns[2]) == strings.ToLower(mac.String()) {
			return net.ParseIP(columns[0]), nil
		}
	}
	return nil, ErrIPNotFound
}
