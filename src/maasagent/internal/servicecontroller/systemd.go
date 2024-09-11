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

	"github.com/rs/zerolog/log"
	"github.com/snapcore/snapd/systemd"
)

type systemdReporter struct{}

func (s systemdReporter) Notify(n string) {
	log.Debug().Msg(n)
}

type SystemdController struct {
	client systemd.Systemd
	unit   string
}

func NewSystemdController(service string) *SystemdController {
	client := systemd.New(systemd.SystemMode, systemdReporter{})

	return &SystemdController{
		unit:   service,
		client: client,
	}
}

func (c *SystemdController) Start(_ context.Context) error {
	return c.client.Start([]string{c.unit})
}

func (c *SystemdController) Stop(_ context.Context) error {
	return c.client.Stop([]string{c.unit})
}

func (c *SystemdController) Restart(_ context.Context) error {
	return c.client.Restart([]string{c.unit})
}

func (c *SystemdController) Status(_ context.Context) (ServiceStatus, error) {
	info, err := c.client.Status([]string{c.unit})
	if err != nil {
		return StatusError, err
	}

	// only one unit requested, so accessed via [0]
	if info[0].Active {
		return StatusRunning, nil
	}

	return StatusStopped, nil
}
