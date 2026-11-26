// Copyright (c) 2025 Canonical Ltd
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

package resolver

import (
	"time"

	"github.com/miekg/dns"
)

// WithConnPoolSize sets the number of connections for each
// configured server, both authoritative and the ones defined
// in resolv.conf for non-auhtoritative queries
func WithConnPoolSize(size int) RecursiveHandlerOption {
	return func(h *RecursiveHandler) {
		if size == 0 {
			return
		}

		h.connPoolSize = size
	}
}

// WithDialTimeout sets the timeout for connecting to an upstream server
func WithDialTimeout(timeout time.Duration) RecursiveHandlerOption {
	return func(h *RecursiveHandler) {
		if timeout == 0 {
			return
		}

		client, ok := h.client.(*dns.Client)
		if !ok { // can only set DialTimeout on *dns.Client
			return
		}

		client.DialTimeout = timeout
	}
}

// WithUDPSize sets the size UDP packet sent to upstream DNS servers
func WithUDPSize(size uint16) RecursiveHandlerOption {
	return func(h *RecursiveHandler) {
		if size == 0 {
			return
		}

		client, ok := h.client.(*dns.Client)
		if !ok {
			return
		}

		client.UDPSize = size
	}
}
