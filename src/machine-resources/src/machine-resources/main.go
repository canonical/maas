// Copyright 2014-2020 Canonical Ltd.  This software is licensed under the
// GNU Affero General Public License version 3 (see the file LICENSE).

package main

import (
	"bufio"
	"encoding/json"
	"fmt"
	"net"
	"os"
	"strings"

	"github.com/lxc/lxd/lxd/resources"
	"github.com/lxc/lxd/shared"
	"github.com/lxc/lxd/shared/version"
)

type OSInfo struct {
	OSName    string `json:"os_name" yaml:"os_name"`
	OSVersion string `json:"os_version" yaml:"os_version"`
}

// Subset of github.com/lxc/lxd/shared/api/server.ServerEnvironment
type ServerEnvironment struct {
	Kernel             string `json:"kernel" yaml:"kernel"`
	KernelArchitecture string `json:"kernel_architecture" yaml:"kernel_architecture"`
	KernelVersion      string `json:"kernel_version" yaml:"kernel_version"`
	OSInfo
	Server        string `json:"server" yaml:"server"`
	ServerName    string `json:"server_name" yaml:"server_name"`
	ServerVersion string `json:"server_version" yaml:"server_version"`
}

// Subset of github.com/lxc/lxd/shared/api/server.HostInfo
type HostInfo struct {
	APIExtensions []string          `json:"api_extensions" yaml:"api_extensions"`
	APIVersion    string            `json:"api_version" yaml:"api_version"`
	Environment   ServerEnvironment `json:"environment" yaml:"environment"`
}

type AllInfo struct {
	HostInfo
	Resources interface{} `json:"resources" yaml:"resources"`
	Networks  interface{} `json:"networks" yaml:"networks"`
}

func checkError(err error) {
	if err == nil {
		return
	}
	fmt.Fprintf(os.Stderr, "ERROR: %v\n", err)
	os.Exit(1)
}

func parseKeyValueFile(path string) (map[string]string, error) {
	parsed_file := make(map[string]string)
	file, err := os.Open(path)
	if err != nil {
		return parsed_file, err
	}
	defer file.Close()

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
		parsed_file[strings.Trim(tokens[0], `'"`)] = strings.Trim(tokens[1], `'"`)
	}

	return parsed_file, nil
}

func getOSNameVersion() OSInfo {
	// Search both pathes as suggested by
	// https://www.freedesktop.org/software/systemd/man/os-release.html
	for _, path := range []string{"/etc/os-release", "/usr/lib/os-release"} {
		parsed_file, err := parseKeyValueFile(path)
		// LP:1876217 - As of 2.44 snapd only gives confined Snaps
		// access to /etc/lsb-release from the host OS. /etc/os-release
		// currently contains the Ubuntu Core version the Snap is
		// running. Try /etc/os-release first for controllers installed
		// with the Debian packages. At some point in the future snapd
		// may provide the host OS version of /etc/os-release.
		if err == nil && parsed_file["ID"] != "ubuntu-core" {
			return OSInfo{
				OSName:    strings.ToLower(parsed_file["ID"]),
				OSVersion: strings.ToLower(parsed_file["VERSION_ID"]),
			}
		}
	}
	// If /etc/os-release isn't found or only contains the Ubuntu Core
	// version try to get OS information from /etc/lsb-release as this
	// file is passed from the running host OS. Only Ubuntu and Manjaro
	// provide /etc/lsb-release.
	parsed_file, err := parseKeyValueFile("/etc/lsb-release")
	if err == nil {
		return OSInfo{
			OSName:    strings.ToLower(parsed_file["DISTRIB_ID"]),
			OSVersion: strings.ToLower(parsed_file["DISTRIB_RELEASE"]),
		}
	} else {
		// If the OS information isn't detectable don't send anything.
		// MAAS will keep the current OS information.
		return OSInfo{}
	}
}

func GetHostInfo() HostInfo {
	hostname, err := os.Hostname()
	checkError(err)

	uname, err := shared.Uname()
	checkError(err)

	return HostInfo{
		// These are the API extensions machine-resources reproduces.
		APIExtensions: []string{
			"resources",
			"resources_cpu_socket",
			"resources_gpu",
			"resources_numa",
			"resources_v2",
			"resources_disk_sata",
			"resources_usb_pci",
			"resources_cpu_threads_numa",
			"resources_cpu_core_die",
			"api_os",
			"resources_system",
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
	}
}

func GetResources() interface{} {
	data, err := resources.GetResources()
	checkError(err)
	return data
}

func GetNetworks() interface{} {
	ifaces, err := net.Interfaces()
	checkError(err)
	data := make(map[string]interface{}, len(ifaces))
	for _, iface := range ifaces {
		netDetails, err := resources.GetNetworkState(iface.Name)
		checkError(err)
		data[iface.Name] = netDetails
	}
	return data
}

func main() {
	data := AllInfo{
		HostInfo:  GetHostInfo(),
		Resources: GetResources(),
		Networks:  GetNetworks(),
	}
	encoder := json.NewEncoder(os.Stdout)
	encoder.SetEscapeHTML(false)
	encoder.SetIndent("", "    ")
	err := encoder.Encode(data)
	checkError(err)
}
