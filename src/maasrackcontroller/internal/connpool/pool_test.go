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

package connpool

import (
	"net"
	"net/netip"
	"sync"
	"testing"
	"time"
)

type fakeConn struct {
	net.Conn
}

func (f *fakeConn) Close() error { return nil }

func BenchmarkConn_Pool(b *testing.B) {
	const conns = 100

	factory := func() (net.Conn, error) {
		return &fakeConn{}, nil
	}

	pool, _ := NewChannelPool(10, factory)

	m := make(map[netip.Addr]Pool)

	ip := netip.MustParseAddr("127.0.0.1")
	m[ip] = pool

	for range 10 {
		conn, _ := m[ip].Get()
		conn.Close()
	}

	doWork := func() {
		var wg sync.WaitGroup

		wg.Add(conns)

		for range conns {
			go func() {
				conn, _ := m[ip].Get()

				time.Sleep(10 * time.Millisecond)
				conn.Close()
				wg.Done()
			}()
		}

		wg.Wait()
	}

	b.ResetTimer()

	for i := 0; i < b.N; i++ {
		doWork()
	}

	if pool.Len() > 10 {
		b.Fail()
	}
}
