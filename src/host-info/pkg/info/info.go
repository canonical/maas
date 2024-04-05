// Copyright (c) 2022-2024 Canonical Ltd
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

//go:build linux
// +build linux

//nolint:stylecheck // ignore ST1000
package info

import (
	"bufio"
	"net"
	"os"
	"path/filepath"
	"strings"

	"github.com/canonical/lxd/lxd/resources"
	"github.com/canonical/lxd/shared"
	lxdapi "github.com/canonical/lxd/shared/api"
	"github.com/canonical/lxd/shared/version"
)

// OSInfo represents OS information
type OSInfo struct {
	OSName    string `json:"os_name" yaml:"os_name"`
	OSVersion string `json:"os_version" yaml:"os_version"`
}

// ServerEnvironment is a subset of github.com/canonical/lxd/shared/api/server.ServerEnvironment
type ServerEnvironment struct {
	Kernel             string `json:"kernel" yaml:"kernel"`
	KernelArchitecture string `json:"kernel_architecture" yaml:"kernel_architecture"`
	KernelVersion      string `json:"kernel_version" yaml:"kernel_version"`
	OSInfo
	Server        string `json:"server" yaml:"server"`
	ServerName    string `json:"server_name" yaml:"server_name"`
	ServerVersion string `json:"server_version" yaml:"server_version"`
}

// HostInfo is a subset of github.com/canonical/lxd/shared/api/server.HostInfo
type HostInfo struct {
	Environment   ServerEnvironment `json:"environment" yaml:"environment"`
	APIVersion    string            `json:"api_version" yaml:"api_version"`
	APIExtensions []string          `json:"api_extensions" yaml:"api_extensions"`
}

type AllInfo struct {
	Resources *lxdapi.Resources      `json:"resources" yaml:"resources"`
	Networks  map[string]interface{} `json:"networks" yaml:"networks"`
	HostInfo
}

func parseKeyValueFile(path string) (map[string]string, error) {
	parsedFile := make(map[string]string)

	file, err := os.Open(filepath.Clean(path))
	if err != nil {
		return parsedFile, err
	}

	defer func() {
		if err := file.Close(); err != nil {
			panic(err)
		}
	}()

	scanner := bufio.NewScanner(file)
	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if strings.HasPrefix(line, "#") {
			continue
		}

		tokens := strings.SplitN(line, "=", 2)
		if len(tokens) != 2 {
			continue
		}

		parsedFile[strings.Trim(tokens[0], `'"`)] = strings.Trim(tokens[1], `'"`)
	}

	return parsedFile, nil
}

func getOSNameVersion() OSInfo {
	// Search both pathes as suggested by
	// https://www.freedesktop.org/software/systemd/man/os-release.html
	for _, path := range []string{"/etc/os-release", "/usr/lib/os-release"} {
		parsedFile, err := parseKeyValueFile(path)
		// LP:1876217 - As of 2.44 snapd only gives confined Snaps
		// access to /etc/lsb-release from the host OS. /etc/os-release
		// currently contains the Ubuntu Core version the Snap is
		// running. Try /etc/os-release first for controllers installed
		// with the Debian packages. At some point in the future snapd
		// may provide the host OS version of /etc/os-release.
		if err == nil && parsedFile["ID"] != "ubuntu-core" {
			return OSInfo{
				OSName:    strings.ToLower(parsedFile["ID"]),
				OSVersion: strings.ToLower(parsedFile["VERSION_ID"]),
			}
		}
	}
	// If /etc/os-release isn't found or only contains the Ubuntu Core
	// version try to get OS information from /etc/lsb-release as this
	// file is passed from the running host OS. Only Ubuntu and Manjaro
	// provide /etc/lsb-release.
	parsedFile, err := parseKeyValueFile("/etc/lsb-release")
	if err != nil {
		return OSInfo{}
	}

	return OSInfo{
		OSName:    strings.ToLower(parsedFile["DISTRIB_ID"]),
		OSVersion: strings.ToLower(parsedFile["DISTRIB_RELEASE"]),
	}
}

func getHostInfo() (*HostInfo, error) {
	hostname, err := os.Hostname()
	if err != nil {
		return nil, err
	}

	uname, err := shared.Uname()
	if err != nil {
		return nil, err
	}

	return &HostInfo{
		// These are the API extensions machine-resources reproduces.
		APIExtensions: []string{
			"resources",
			"resources_cpu_socket",
			"resources_gpu",
			"resources_numa",
			"resources_v2",
			"resources_disk_sata",
			"resources_network_firmware",
			"resources_disk_id",
			"resources_usb_pci",
			"resources_cpu_threads_numa",
			"resources_cpu_core_die",
			"api_os",
			"resources_system",
			"resources_pci_iommu",
			"resources_network_usb",
			"resources_disk_address",
		},
		// machine-resources leverages LXD API code to output data. If
		// the LXD import is updated and this changes MAAS may need to
		// be updated. The metadata server checks this value.
		APIVersion: version.APIVersion,
		Environment: ServerEnvironment{
			Kernel:             uname.Sysname,
			KernelArchitecture: uname.Machine,
			KernelVersion:      uname.Release,
			OSInfo:             getOSNameVersion(),
			Server:             "maas-machine-resources",
			ServerName:         hostname,
			// Use the imported LXD version as the data comes from
			// there.
			ServerVersion: version.Version,
		},
	}, nil
}

func getResources() (*lxdapi.Resources, error) {
	return resources.GetResources()
}

func getNetworks() (map[string]interface{}, error) {
	ifaces, err := net.Interfaces()
	if err != nil {
		return nil, err
	}

	data := make(map[string]interface{}, len(ifaces))

	for _, iface := range ifaces {
		netDetails, err := resources.GetNetworkState(iface.Name)
		if err != nil {
			return nil, err
		}

		data[iface.Name] = netDetails
	}

	return data, nil
}

func GetInfo() (*AllInfo, error) {
	hostInfo, err := getHostInfo()
	if err != nil {
		return nil, err
	}

	resInfo, err := getResources()
	if err != nil {
		return nil, err
	}

	netInfo, err := getNetworks()
	if err != nil {
		return nil, err
	}

	return &AllInfo{
		HostInfo:  *hostInfo,
		Resources: resInfo,
		Networks:  netInfo,
	}, nil
}
