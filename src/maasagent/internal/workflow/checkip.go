// Copyright (c) 2023-2024 Canonical Ltd
//
// This program is free software: you can redistribute it and/or modify
// it under the terms of the GNU Affero General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.
//
// This program is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
// GNU Affero General Public License for more details.
//
// You should have received a copy of the GNU Affero General Public License
// along with this program.  If not, see <http://www.gnu.org/licenses/>.

package workflow

import (
	"net"
	"net/netip"
	"time"

	"go.temporal.io/sdk/workflow"

	"maas.io/core/src/maasagent/internal/netmon"
)

// CheckIPParam is a workflow parameter for the CheckIP workflow
type CheckIPParam struct {
	IPs []netip.Addr `json:"ips"`
}

// CheckIPResult is a value returned by the CheckIP workflow
type CheckIPResult struct {
	IPs map[netip.Addr]net.HardwareAddr `json:"ips"`
}

// CheckIP is a Temporal workflow for checking available IP addresses
func CheckIP(ctx workflow.Context, param CheckIPParam) (CheckIPResult, error) {
	ao := workflow.LocalActivityOptions{
		ScheduleToCloseTimeout: 5 * time.Second,
	}
	ctx = workflow.WithLocalActivityOptions(ctx, ao)

	var scanned map[netip.Addr]net.HardwareAddr

	err := workflow.ExecuteLocalActivity(ctx, netmon.Scan, param.IPs).Get(ctx, &scanned)
	if err != nil {
		return CheckIPResult{}, err
	}

	result := CheckIPResult{
		IPs: scanned,
	}

	return result, nil
}
