package machinehelpers

import (
	"path/filepath"
	"runtime"
)

func isDevEnv() bool {
	// TODO grab this value from config
	return true
}

// GetResourcesBinPath returns the expected path for the machine-resources binary
func GetResourcesBinPath() (string, error) {
	var path string
	if isDevEnv() {
		path = "src/machine-resources/bin"
	} else {
		prefix, ok := SnapPaths{}.FromEnv()["snap"]
		path = "/usr/share/maas/machine-resources"
		if ok {
			path = prefix + path
		}
	}
	absPath, err := filepath.Abs(path)
	if err != nil {
		return "", err
	}
	return filepath.Join(absPath, runtime.GOARCH), nil
}
