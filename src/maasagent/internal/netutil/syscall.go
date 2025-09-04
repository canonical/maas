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

package netutil

import "syscall"

// Syscaller is an interface used for testing purposes where mock of syscall
// package functions is needed
type Syscaller interface {
	Close(fd int) error
	Sendto(fd int, p []byte, flags int, to syscall.Sockaddr) error
	SetsockoptInt(fd, level, opt int, value int) error
	Socket(domain, typ, proto int) (fd int, err error)
}

// RealSyscaller implements Syscaller using real syscalls
type RealSyscaller struct{}

func (RealSyscaller) Close(fd int) error {
	return syscall.Close(fd)
}

func (RealSyscaller) Sendto(fd int, p []byte, flags int, to syscall.Sockaddr) error {
	return syscall.Sendto(fd, p, flags, to)
}

func (RealSyscaller) SetsockoptInt(fd, level, opt int, value int) error {
	return syscall.SetsockoptInt(fd, level, opt, value)
}

func (RealSyscaller) Socket(domain, typ, proto int) (int, error) {
	return syscall.Socket(domain, typ, proto)
}
