package machinehelpers

import (
	"os"
)

var (
	pathVars = map[string]string{
		"snap":   "SNAP",
		"common": "SNAP_COMMON",
		"data":   "SNAP_DATA",
	}
)

// IsRunningInSnap looks for the SNAP env variable, if set, it is assumed the running process is within a snap
func IsRunningInSnap() bool {
	_, ok := os.LookupEnv("SNAP")
	return ok
}

// SnapPaths provides lookup for given snap paths
type SnapPaths map[string]string

func (s SnapPaths) FromEnv() SnapPaths {
	for k, v := range pathVars {
		path, ok := os.LookupEnv(v)
		if ok {
			s[k] = path
		}
	}
	return s
}
