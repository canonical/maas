package machinehelpers

import (
	lxdresources "github.com/lxc/lxd/shared/api"
)

type EnvInfo struct {
	Kernel             string `json:"kernel"`
	KernelArchitecture string `json:"kernel_architecture"`
	KernelVersion      string `json:"kernel_version"`
	OSName             string `json:"os_name"`
	OSVersion          string `json:"os_version"`
	Server             string `json:"server"`
	ServerName         string `json:"server_name"`
	ServerVersion      string `json:"server_version"`
}

// MachineInfo correlates with the printed value from machine-resources
type MachineInfo struct {
	APIExtensions []string                             `json:"api_extension"`
	APIVersion    string                               `json:"api_version"`
	Environment   EnvInfo                              `json:"environment"`
	Resources     lxdresources.Resources               `json:"resources"`
	Networks      map[string]lxdresources.NetworkState `json:"networks"`
}
