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

package testing

import (
	"os"
	"testing"

	lxdc "github.com/canonical/lxd/client"
	lxdapi "github.com/canonical/lxd/shared/api"
)

type LXDContainer struct {
	t      testing.TB
	client lxdc.InstanceServer
	name   string
}

// NewLXDContainer is a test helper that creates LXD container with provided
// name and image. It can be used for various purposes of during integration tests.
// Container tear-down happens automatically using t.Cleanup()
func NewLXDContainer(t testing.TB, name, image string) *LXDContainer {
	t.Helper()

	c := getLXDClient(t)

	req := lxdapi.ContainersPost{
		Name: name,
		Source: lxdapi.ContainerSource{
			Type:        "image",
			Fingerprint: getLXDImage(t, c, image).Fingerprint,
		},
	}

	op, err := c.CreateContainer(req)
	if err != nil {
		t.Fatalf("failed to create LXD container: %v", err)
	}

	// Wait for the operation to complete
	err = op.Wait()
	if err != nil {
		t.Fatalf("failed to create LXD container: %v", err)
	}

	container := LXDContainer{t: t, name: name, client: c}

	container.startLXDContainer()

	t.Cleanup(func() {
		container.stopLXDContainer()

		op, err := c.DeleteContainer(name)
		if err != nil {
			t.Fatalf("failed to delete LXD container: %v", err)
			return
		}

		err = op.Wait()
		if err != nil {
			t.Fatalf("failed to delete LXD container: %v", err)
		}
	})

	return &container
}

// Exec will execute provided command inside container
func (c *LXDContainer) Exec(command []string) {
	c.t.Helper()

	// Setup the exec request
	req := lxdapi.InstanceExecPost{
		Command:   command,
		WaitForWS: true,
	}

	args := lxdc.InstanceExecArgs{
		Stdin:  os.Stdin,
		Stdout: os.Stdout,
		Stderr: os.Stderr,
	}

	op, err := c.client.ExecInstance(c.name, req, &args)
	if err != nil {
		c.t.Fatalf("failed to execute command: %v", err)
	}

	// Wait for it to complete
	err = op.Wait()
	if err != nil {
		c.t.Fatalf("failed to execute command: %v", err)
	}
}

func (c *LXDContainer) Network() map[string]lxdapi.ContainerStateNetwork {
	state, _, err := c.client.GetContainerState(c.name)
	if err != nil {
		c.t.Fatalf("failed to get container: %v", err)
	}

	return state.Network
}

func (c *LXDContainer) startLXDContainer() {
	c.t.Helper()

	req := lxdapi.InstanceStatePut{
		Action:  "start",
		Timeout: -1,
	}

	op, err := c.client.UpdateInstanceState(c.name, req, "")
	if err != nil {
		c.t.Fatalf("failed to start LXD container: %v", err)
	}

	err = op.Wait()
	if err != nil {
		c.t.Fatalf("failed to start LXD container: %v", err)
	}
}

func (c *LXDContainer) stopLXDContainer() {
	c.t.Helper()

	req := lxdapi.InstanceStatePut{
		Action:  "stop",
		Force:   true,
		Timeout: -1,
	}

	op, err := c.client.UpdateInstanceState(c.name, req, "")
	if err != nil {
		c.t.Fatalf("failed to stop LXD container: %v", err)
	}

	err = op.Wait()
	if err != nil {
		c.t.Fatalf("failed to stop LXD container: %v", err)
	}
}

func getLXDClient(t testing.TB) lxdc.InstanceServer {
	t.Helper()
	// Connect to LXD over the Unix socket
	c, err := lxdc.ConnectLXDUnix("/var/snap/lxd/common/lxd/unix.socket", nil)
	if err != nil {
		t.Fatalf("failed to connect to LXD: %v", err)
	}

	return c
}

func getLXDImage(t testing.TB, c lxdc.InstanceServer, name string) *lxdapi.Image {
	t.Helper()
	// Connect to the remote SimpleStreams server
	d, err := lxdc.ConnectSimpleStreams("https://cloud-images.ubuntu.com/releases", nil)
	if err != nil {
		t.Fatalf("failed to connect to simplestreams: %v", err)
	}

	// Resolve the alias
	alias, _, err := d.GetImageAlias(name)
	if err != nil {
		t.Fatalf("failed to get image alias: %v", err)
	}

	// Get the image information
	image, _, err := d.GetImage(alias.Target)
	if err != nil {
		t.Fatalf("failed to get image: %v", err)
	}

	// Ask LXD to copy the image from the remote server
	op, err := c.CopyImage(d, *image, nil)
	if err != nil {
		t.Fatalf("failed to copy image: %v", err)
	}

	// And wait for it to finish
	err = op.Wait()
	if err != nil {
		t.Fatalf("failed to get image: %v", err)
	}

	return image
}
