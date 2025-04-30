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

// The MIT License (MIT)
//
// Copyright (c) 2013 Fatih Arslan
//
// Permission is hereby granted, free of charge, to any person obtaining a copy of
// this software and associated documentation files (the "Software"), to deal in
// the Software without restriction, including without limitation the rights to
// use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
// the Software, and to permit persons to whom the Software is furnished to do so,
// subject to the following conditions:
//
// The above copyright notice and this permission notice shall be included in all
// copies or substantial portions of the Software.
//
// THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
// IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
// FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
// COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
// IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
// CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

package connpool

import (
	"io"
	"math/rand/v2"
	"net"
	"sync"
	"testing"
	"time"

	"github.com/stretchr/testify/require"
)

var (
	maxCap  = 30
	factory = func(addr string) Factory {
		return func() (net.Conn, error) { return net.Dial("tcp", addr) }
	}
)

func startTestTCPServer(t *testing.T) (string, func()) {
	ln, err := net.Listen("tcp", "127.0.0.1:0") // :0 picks an available port
	require.NoError(t, err)

	go func() {
		for {
			conn, err := ln.Accept()
			if err != nil {
				return // shutdown
			}

			go func(c net.Conn) {
				defer c.Close()

				io.Copy(c, c)
			}(conn)
		}
	}()

	return ln.Addr().String(), func() {
		_ = ln.Close()
	}
}

func TestNew(t *testing.T) {
	addr, shutdown := startTestTCPServer(t)
	defer shutdown()

	_, err := NewChannelPool(maxCap, factory(addr))
	if err != nil {
		t.Errorf("New error: %s", err)
	}
}

func TestPool_Get(t *testing.T) {
	addr, shutdown := startTestTCPServer(t)
	defer shutdown()

	p, _ := NewChannelPool(maxCap, factory(addr))
	defer p.Close()

	conn, err := p.Get()
	if err != nil {
		t.Errorf("Get error: %s", err)
	}

	if conn == nil {
		t.Errorf("Get error: conn is nil")
	}

	// After one get, there should still be no connections available.
	if p.Len() != 0 {
		t.Errorf("Get error. Expecting %d, got %d", 0, p.Len())
	}
}

func TestPool_Put(t *testing.T) {
	addr, shutdown := startTestTCPServer(t)
	defer shutdown()

	p, err := NewChannelPool(30, factory(addr))
	if err != nil {
		t.Fatal(err)
	}
	defer p.Close()

	// get/create from the pool
	conns := make([]net.Conn, maxCap)

	for i := range maxCap {
		conn, _ := p.Get()
		conns[i] = conn
	}

	// now put them all back
	for _, conn := range conns {
		conn.Close()
	}

	if p.Len() != maxCap {
		t.Errorf("Put error len. Expecting %d, got %d",
			1, p.Len())
	}

	conn, _ := p.Get()
	p.Close() // close pool

	conn.Close() // try to put into a full pool

	if p.Len() != 0 {
		t.Errorf("Put error. Closed pool shouldn't allow to put connections.")
	}
}

func TestPool_PutUnusableConn(t *testing.T) {
	addr, shutdown := startTestTCPServer(t)
	defer shutdown()

	p, _ := NewChannelPool(maxCap, factory(addr))
	defer p.Close()

	// ensure pool is not empty
	conn, _ := p.Get()
	conn.Close()

	poolSize := p.Len()
	conn, _ = p.Get()
	conn.Close()

	if p.Len() != poolSize {
		t.Errorf("Pool size is expected to be equal to initial size")
	}

	conn, _ = p.Get()
	if pc, ok := conn.(*Conn); !ok {
		t.Errorf("Impossible")
	} else {
		pc.MarkUnusable()
	}

	conn.Close()

	if p.Len() != poolSize-1 {
		t.Errorf("Pool size is expected to be initial_size - 1, %d, %d", p.Len(), poolSize-1)
	}
}

func TestPool_UsedCapacity(t *testing.T) {
	addr, shutdown := startTestTCPServer(t)
	defer shutdown()

	p, _ := NewChannelPool(maxCap, factory(addr))
	defer p.Close()

	if p.Len() != 0 {
		t.Errorf("maxCap error. Expecting %d, got %d", 0, p.Len())
	}
}

func TestPool_Close(t *testing.T) {
	addr, shutdown := startTestTCPServer(t)
	defer shutdown()

	p, _ := NewChannelPool(maxCap, factory(addr))

	// now close it and test all cases we are expecting.
	p.Close()

	c := p.(*channelPool)

	if c.conns != nil {
		t.Errorf("Close error, conns channel should be nil")
	}

	if c.factory != nil {
		t.Errorf("Close error, factory should be nil")
	}

	_, err := p.Get()
	if err == nil {
		t.Errorf("Close error, get conn should return an error")
	}

	if p.Len() != 0 {
		t.Errorf("Close error used capacity. Expecting 0, got %d", p.Len())
	}
}

func TestPoolConcurrent(t *testing.T) {
	addr, shutdown := startTestTCPServer(t)
	defer shutdown()

	p, _ := NewChannelPool(maxCap, factory(addr))
	pipe := make(chan net.Conn)

	go func() {
		p.Close()
	}()

	for range maxCap {
		go func() {
			conn, _ := p.Get()

			pipe <- conn
		}()

		go func() {
			conn := <-pipe
			if conn == nil {
				return
			}

			conn.Close()
		}()
	}
}

func TestPoolWriteRead(t *testing.T) {
	addr, shutdown := startTestTCPServer(t)
	defer shutdown()

	p, _ := NewChannelPool(30, factory(addr))

	conn, _ := p.Get()

	msg := "hello"

	_, err := conn.Write([]byte(msg))
	if err != nil {
		t.Error(err)
	}
}

func TestPoolConcurrent2(t *testing.T) {
	addr, shutdown := startTestTCPServer(t)
	defer shutdown()

	p, _ := NewChannelPool(30, factory(addr))

	var wg sync.WaitGroup

	wg.Add(10)

	go func() {
		for i := range 10 {
			go func(i int) {
				conn, _ := p.Get()

				time.Sleep(rand.N(100 * time.Millisecond))
				conn.Close()
				wg.Done()
			}(i)
		}
	}()

	for i := range 10 {
		wg.Add(1)

		go func(i int) {
			conn, _ := p.Get()

			time.Sleep(rand.N(100 * time.Millisecond))
			conn.Close()
			wg.Done()
		}(i)
	}

	wg.Wait()
}

func TestPoolConcurrent3(t *testing.T) {
	addr, shutdown := startTestTCPServer(t)
	defer shutdown()

	p, _ := NewChannelPool(1, factory(addr))

	var wg sync.WaitGroup

	wg.Add(1)

	go func() {
		p.Close()
		wg.Done()
	}()

	if conn, err := p.Get(); err == nil {
		conn.Close()
	}

	wg.Wait()
}
