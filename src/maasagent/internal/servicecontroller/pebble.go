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
	"os"
	"path"
	"time"

	pebble "github.com/canonical/pebble/client"
)

type pebbleClient interface {
	Start(*pebble.ServiceOptions) (string, error)
	Stop(*pebble.ServiceOptions) (string, error)
	Restart(*pebble.ServiceOptions) (string, error)
	Services(*pebble.ServicesOptions) ([]*pebble.ServiceInfo, error)
	WaitChange(string, *pebble.WaitChangeOptions) (*pebble.Change, error)
}

type PebbleController struct {
	config  pebble.Config
	client  pebbleClient
	service string
}

func NewPebbleController(service string) (*PebbleController, error) {
	pebbleRoot := os.Getenv("PEBBLE")
	socket, ok := os.LookupEnv("PEBBLE_SOCKET")

	if !ok {
		socket = path.Join(pebbleRoot, ".pebble.socket")
	}

	pebbleCtrlr := &PebbleController{
		service: service}

	pebbleCtrlr.config = pebble.Config{
		Socket: socket,
	}

	client, err := pebble.New(&pebbleCtrlr.config)
	if err != nil {
		return nil, err
	}

	pebbleCtrlr.client = client

	return pebbleCtrlr, nil
}

func (c *PebbleController) waitForCmd(ctx context.Context, changeID string) error {
	opts := &pebble.WaitChangeOptions{}

	deadline, ok := ctx.Deadline()
	if ok {
		opts.Timeout = time.Until(deadline)
	}

	_, err := c.client.WaitChange(changeID, opts)

	return err
}

func (c *PebbleController) Start(ctx context.Context) error {
	changeID, err := c.client.Start(&pebble.ServiceOptions{Names: []string{c.service}})
	if err != nil {
		return err
	}

	return c.waitForCmd(ctx, changeID)
}

func (c *PebbleController) Stop(ctx context.Context) error {
	changeID, err := c.client.Stop(&pebble.ServiceOptions{Names: []string{c.service}})
	if err != nil {
		return err
	}

	return c.waitForCmd(ctx, changeID)
}

func (c *PebbleController) Restart(ctx context.Context) error {
	changeID, err := c.client.Restart(&pebble.ServiceOptions{Names: []string{c.service}})
	if err != nil {
		return err
	}

	return c.waitForCmd(ctx, changeID)
}

func (c *PebbleController) Status(_ context.Context) (ServiceStatus, error) {
	serviceInfo, err := c.client.Services(&pebble.ServicesOptions{Names: []string{c.service}})
	if err != nil {
		return StatusUnknown, err
	}

	// only one unit requested, so accessed via [0]
	status := serviceInfo[0].Current

	switch status {
	case pebble.StatusActive:
		return StatusRunning, nil
	case pebble.StatusInactive:
		return StatusStopped, nil
	case pebble.StatusError, pebble.StatusBackoff:
		return StatusError, nil
	default:
		return StatusUnknown, nil
	}
}
