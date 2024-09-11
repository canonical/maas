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
)

type Controller interface {
	Start(context.Context) error
	Stop(context.Context) error
	Restart(context.Context) error
	Status(context.Context) (ServiceStatus, error)
}

type ServiceStatus int

//go:generate go run golang.org/x/tools/cmd/stringer -type=ServiceStatus -trimprefix=Status

const (
	StatusUnknown ServiceStatus = iota
	StatusRunning
	StatusStopped
	StatusError
)

func NewController(service string) (Controller, error) {
	if _, ok := os.LookupEnv("SNAP"); ok {
		return NewPebbleController(service)
	}

	return NewSystemdController(service), nil
}
