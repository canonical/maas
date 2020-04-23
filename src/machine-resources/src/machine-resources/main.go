// Copyright 2014-2020 Canonical Ltd.  This software is licensed under the
// GNU Affero General Public License version 3 (see the file LICENSE).

package main

import (
	"encoding/json"
	"fmt"
	"os"

	"github.com/lxc/lxd/lxd/resources"
	"github.com/lxc/lxd/shared"
	"github.com/lxc/lxd/shared/osarch"
	"github.com/lxc/lxd/shared/version"
)

// Subset of github.com/lxc/lxd/shared/api/server.ServerEnvironment
type ServerEnvironment struct {
	Kernel             string `json:"kernel" yaml:"kernel"`
	KernelArchitecture string `json:"kernel_architecture" yaml:"kernel_architecture"`
	KernelVersion      string `json:"kernel_version" yaml:"kernel_version"`
	OSName             string `json:"os_name" yaml:"os_name"`
	OSVersion          string `json:"os_version" yaml:"os_version"`
	Server             string `json:"server" yaml:"server"`
	ServerName         string `json:"server_name" yaml:"server_name"`
	ServerVersion      string `json:"server_version" yaml:"server_version"`
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
}

func check_error(err error) {
	if err != nil {
		fmt.Fprintf(os.Stderr, "ERROR: %v\n", err)
		os.Exit(1)
	}
}

func GetHostInfo() HostInfo {
	hostname, err := os.Hostname()
	check_error(err)

	uname, err := shared.Uname()
	check_error(err)

	osInfo, err := osarch.GetLSBRelease()
	check_error(err)

	return HostInfo{
		// These are the API extensions machine-resources reproduces.
		APIExtensions: []string{
			"resources",
			"resources_v2",
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
			OSName:             osInfo["NAME"],
			OSVersion:          osInfo["VERSION_ID"],
			Server:             "maas-machine-resources",
			ServerName:         hostname,
			// Use the imported LXD version as the data comes from
			// there.
			ServerVersion: version.Version,
		},
	}
}

func GetResources() (resources_data interface{}) {
	var err error
	resources_data, err = resources.GetResources()
	check_error(err)
	return
}

func help() {
	fmt.Fprintf(os.Stderr, "usage: %s <endpoint> - Output system information in JSON\n\n", os.Args[0])
	fmt.Fprintf(os.Stderr, "Supported LXD API endpoints:\n")
	fmt.Fprintf(os.Stderr, "/            Print host info\n")
	fmt.Fprintf(os.Stderr, "/resources   Print system resources\n")
	fmt.Fprintf(os.Stderr, "/networks    Print network information\n\n")
	fmt.Fprintf(os.Stderr, "Default      Print all information combined\n")
	os.Exit(1)
}

func main() {
	var data interface{}
	var err error
	switch len(os.Args) {
	case 1:
		data = AllInfo{
			HostInfo:  GetHostInfo(),
			Resources: GetResources(),
		}
	case 2:
		switch os.Args[1] {
		case "/":
			data = GetHostInfo()
		case "/resources":
			data = GetResources()
		case "/networks":
			fmt.Fprintf(os.Stderr, "TODO: Show network information\n")
			os.Exit(1)
		case "help":
			help()
		default:
			fmt.Fprintf(os.Stderr, "ERROR: Unknown endpoint '%s'!\n\n", os.Args[1])
			help()
		}
	default:
		fmt.Fprintf(os.Stderr, "ERROR: Too many arguments given!\n\n")
		help()
	}

	ret, err := json.MarshalIndent(data, "", "    ")
	check_error(err)
	fmt.Printf("%s\n", ret)
}
