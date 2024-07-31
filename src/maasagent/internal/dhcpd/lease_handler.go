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
	"container/heap"
	"context"
	"encoding/json"
	"net"

	"github.com/rs/zerolog/log"
)

type Notification struct {
	Action    string           `json:"action"`
	IPFamily  string           `json:"ip_family"`
	Hostname  string           `json:"hostname"`
	MAC       net.HardwareAddr `json:"mac"`
	IP        net.IP           `json:"ip"`
	Timestamp int64            `json:"timestamp"`
	LeaseTime int64            `json:"lease_time"`
}

type LeaseHandler struct {
	conn       net.Conn
	store      *LeaseHeap
	socketPath string
}

func NewLeaseHandler(sockPath string, leaseHeap *LeaseHeap) *LeaseHandler {
	return &LeaseHandler{
		socketPath: sockPath,
		store:      leaseHeap,
	}
}

func (l *LeaseHandler) Read(ctx context.Context) (<-chan Notification, <-chan error) {
	notifications := make(chan Notification)
	errorChan := make(chan error)

	go func() {
		decoder := json.NewDecoder(l.conn)

		defer close(notifications)
		defer close(errorChan)

		for {
			select {
			case <-ctx.Done():
				return
			default:
				var notification Notification

				err := decoder.Decode(&notification)
				if err != nil {
					errorChan <- err
				} else {
					notifications <- notification
				}
			}
		}
	}()

	return notifications, errorChan
}

func (l *LeaseHandler) Start(ctx context.Context) error {
	if l.conn == nil { // For overriding the connection
		addr, err := net.ResolveUnixAddr("unixgram", l.socketPath)
		if err != nil {
			return err
		}

		l.conn, err = net.ListenUnixgram("unixgram", addr)
		if err != nil {
			return err
		}

		defer func() {
			cErr := l.conn.Close()
			if cErr != nil && err == nil {
				err = cErr
			}
		}()
	}

	notifications, errorChan := l.Read(ctx)

	for {
		select {
		case <-ctx.Done():
			return nil
		case notification := <-notifications:
			heap.Push(l.store, notification)
		case err := <-errorChan:
			log.Error().Err(err).Send()
		}
	}
}
