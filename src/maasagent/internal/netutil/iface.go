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

import "net"

func IfaceHasIPv4(iface *net.Interface) (bool, error) {
	addrs, err := iface.Addrs()
	if err != nil {
		return false, err
	}

	for _, addr := range addrs {
		// Current implementation of (net.Interface).Addrs always returns net.IPNet
		if ipNet, ok := addr.(*net.IPNet); ok && ipNet.IP.To4() != nil {
			return true, nil
		}
	}

	return false, nil
}

func IfaceHasIPv6(iface *net.Interface) (bool, error) {
	addrs, err := iface.Addrs()
	if err != nil {
		return false, err
	}

	for _, addr := range addrs {
		// Current implementation of (net.Interface).Addrs always returns net.IPNet
		if ipNet, ok := addr.(*net.IPNet); ok && ipNet.IP.To16() != nil && ipNet.IP.To4() == nil {
			return true, nil
		}
	}

	return false, nil
}
