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

package servicecontroller

import (
	"context"
	"fmt"
	"os/exec"
	"strings"
)

const systemctlBin = "/bin/systemctl"

type client interface {
	OutputSystemctlCommand(context.Context, ...string) (string, error)
	CombinedOutputSystemctlCommand(context.Context, ...string) (string, error)
}

type systemdClient struct{}

func (s *systemdClient) OutputSystemctlCommand(ctx context.Context, args ...string) (string, error) {
	args = append([]string{systemctlBin}, args...)
	cmd := exec.CommandContext(ctx, "sudo", args...)

	out, err := cmd.Output()

	return string(out), err
}

func (s *systemdClient) CombinedOutputSystemctlCommand(ctx context.Context, args ...string) (string, error) {
	args = append([]string{systemctlBin}, args...)
	cmd := exec.CommandContext(ctx, "sudo", args...)

	out, err := cmd.CombinedOutput()

	return string(out), err
}

type SystemdController struct {
	client client
	unit   string
}

func NewSystemdController(service string) *SystemdController {
	return &SystemdController{
		client: &systemdClient{},
		unit:   service,
	}
}

func (c *SystemdController) Start(ctx context.Context) error {
	out, err := c.client.CombinedOutputSystemctlCommand(ctx, "start", c.unit)
	if err != nil {
		return fmt.Errorf("failed to start %s, out: %s, err: %w", c.unit, string(out), err)
	}

	return nil
}

func (c *SystemdController) Stop(ctx context.Context) error {
	out, err := c.client.CombinedOutputSystemctlCommand(ctx, "stop", c.unit)
	if err != nil {
		return fmt.Errorf("failed to stop %s, out: %s, err: %w", c.unit, string(out), err)
	}

	return nil
}

func (c *SystemdController) Restart(ctx context.Context) error {
	out, err := c.client.CombinedOutputSystemctlCommand(ctx, "restart", c.unit)
	if err != nil {
		return fmt.Errorf("failed to restart %s, out: %s, err: %w", c.unit, string(out), err)
	}

	return nil
}

func (c *SystemdController) Status(ctx context.Context) (ServiceStatus, error) {
	out, err := c.client.OutputSystemctlCommand(ctx, "show", c.unit)
	if err != nil {
		return StatusError, fmt.Errorf("failed to fetch service %s status, out: %s, err: %w", c.unit, out, err)
	}

	for _, line := range strings.Split(out, "\n") {
		lineKV := strings.Split(line, "=")
		k, v := lineKV[0], lineKV[1]

		if k == "ActiveState" {
			if v == "active" {
				return StatusRunning, nil
			}

			return StatusStopped, nil
		}
	}

	return StatusUnknown, nil
}
