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

package dhcpd

import (
	"context"
	"os"
	"path"
	"time"

	pebble "github.com/canonical/pebble/client"
	"github.com/rs/zerolog/log"
	"github.com/snapcore/snapd/systemd"
)

type DhcpdVersion int

const (
	DhcpdVersionUnknown DhcpdVersion = iota
	DhcpdVersion4
	DhcpdVersion6
)

type DhcpdStatus int

const (
	DhcpdStatusUnknown DhcpdStatus = iota
	DhcpdStatusRunning
	DhcpdStatusStopped
	DhcpdStatusError
)

type DhcpdController interface {
	Start(context.Context) error
	Stop(context.Context) error
	Restart(context.Context) error
	Status(context.Context) (DhcpdStatus, error)
}

func NewDhcpdController(version DhcpdVersion) (DhcpdController, error) {
	if _, ok := os.LookupEnv("SNAP"); ok {
		cfg := newPebbleConfigFromEnv()

		return newPebbleController(version, cfg)
	}

	return newSystemdController(version), nil
}

type systemdReporter struct{}

func (s systemdReporter) Notify(n string) {
	log.Debug().Msg(n)
}

type systemdController struct {
	client systemd.Systemd
	unit   string
}

func newSystemdController(version DhcpdVersion) DhcpdController {
	client := systemd.New(systemd.SystemMode, systemdReporter{})

	if version == DhcpdVersion4 {
		return &systemdController{
			unit:   "dhcpd.service",
			client: client,
		}
	}

	return &systemdController{
		unit:   "dhcpd6.service",
		client: client,
	}
}

func (s *systemdController) Start(_ context.Context) error {
	return s.client.Start([]string{s.unit})
}

func (s *systemdController) Stop(_ context.Context) error {
	return s.client.Stop([]string{s.unit})
}

func (s *systemdController) Restart(_ context.Context) error {
	return s.client.Restart([]string{s.unit})
}

func (s *systemdController) Status(_ context.Context) (DhcpdStatus, error) {
	info, err := s.client.Status([]string{s.unit})
	if err != nil {
		return DhcpdStatusError, err
	}

	// only one unit requested, so accessed via [0]
	if info[0].Active {
		return DhcpdStatusRunning, nil
	}

	return DhcpdStatusStopped, nil
}

type pebbleClient interface {
	Start(*pebble.ServiceOptions) (string, error)
	Stop(*pebble.ServiceOptions) (string, error)
	Restart(*pebble.ServiceOptions) (string, error)
	Services(*pebble.ServicesOptions) ([]*pebble.ServiceInfo, error)
	WaitChange(string, *pebble.WaitChangeOptions) (*pebble.Change, error)
}

type pebbleController struct {
	client  pebbleClient
	service string
}

func newPebbleConfigFromEnv() *pebble.Config {
	pebbleRoot := os.Getenv("PEBBLE")

	socket, ok := os.LookupEnv("PEBBLE_SOCKET")
	if !ok {
		socket = path.Join(pebbleRoot, ".pebble.socket")
	}

	return &pebble.Config{
		Socket: socket,
	}
}

func newPebbleController(version DhcpdVersion, cfg *pebble.Config) (*pebbleController, error) {
	client, err := pebble.New(cfg)
	if err != nil {
		return nil, err
	}

	if version == DhcpdVersion4 {
		return &pebbleController{
			client:  client,
			service: "dhcpd",
		}, nil
	}

	return &pebbleController{
		client:  client,
		service: "dhcpd6",
	}, nil
}

func (p *pebbleController) waitForCmd(ctx context.Context, changeID string) error {
	opts := &pebble.WaitChangeOptions{}

	deadline, ok := ctx.Deadline()
	if ok {
		opts.Timeout = time.Until(deadline)
	}

	_, err := p.client.WaitChange(changeID, opts)

	return err
}

func (p *pebbleController) Start(ctx context.Context) error {
	changeID, err := p.client.Start(&pebble.ServiceOptions{Names: []string{p.service}})
	if err != nil {
		return err
	}

	return p.waitForCmd(ctx, changeID)
}

func (p *pebbleController) Stop(ctx context.Context) error {
	changeID, err := p.client.Stop(&pebble.ServiceOptions{Names: []string{p.service}})
	if err != nil {
		return err
	}

	return p.waitForCmd(ctx, changeID)
}

func (p *pebbleController) Restart(ctx context.Context) error {
	changeID, err := p.client.Restart(&pebble.ServiceOptions{Names: []string{p.service}})
	if err != nil {
		return err
	}

	return p.waitForCmd(ctx, changeID)
}

func (p *pebbleController) Status(_ context.Context) (DhcpdStatus, error) {
	serviceInfo, err := p.client.Services(&pebble.ServicesOptions{Names: []string{p.service}})
	if err != nil {
		return DhcpdStatusUnknown, err
	}

	// only one unit requested, so accessed via [0]
	status := serviceInfo[0].Current

	switch status {
	case pebble.StatusActive:
		return DhcpdStatusRunning, nil
	case pebble.StatusInactive:
		return DhcpdStatusStopped, nil
	case pebble.StatusError, pebble.StatusBackoff:
		return DhcpdStatusError, nil
	default:
		return DhcpdStatusUnknown, nil
	}
}
