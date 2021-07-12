package machinehelpers

import (
	"fmt"
	"io"
	"os"
	"path/filepath"
	"strings"
	"sync"
)

var (
	maasId string
)

var (
	maasIdLock = &sync.RWMutex{}
)

// GetMAASDataPath returns the path to the directory for MAAS' non-database data
func GetMAASDataPath(path string) string {
	basePath, ok := os.LookupEnv("MAAS_DATA")
	if !ok {
		basePath = "/var/lib/maas"
	}
	return filepath.Join(basePath, path)
}

// GetMAASID returns the MAAS cluster uuid associated with the rack controller
func GetMAASID() (string, error) {
	maasIdLock.Lock()
	defer maasIdLock.Unlock()
	if len(maasId) == 0 {
		path := GetMAASDataPath("maas_id")
		f, err := os.Open(path)
		if err != nil {
			if os.IsNotExist(err) {
				return "", nil
			}
			return "", err
		}
		contents, err := io.ReadAll(f)
		if err != nil {
			return "", err
		}
		maasId = strings.TrimSpace(string(contents))
	}
	return maasId, nil
}

// SetMAASId writes the MAAS cluster uuid to disk
func SetMAASId(id string) error {
	path := GetMAASDataPath("maas_id")
	maasIdLock.Lock()
	defer maasIdLock.Unlock()
	maasId = id
	f, err := os.OpenFile(path, os.O_CREATE|os.O_RDWR, 0644)
	if err != nil {
		return err
	}
	defer f.Close()
	_, err = fmt.Fprint(f, id)
	if err != nil {
		return err
	}
	return nil
}
