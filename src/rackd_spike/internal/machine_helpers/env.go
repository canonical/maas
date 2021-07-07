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

func GetMAASDataPath(path string) string {
	basePath, ok := os.LookupEnv(path)
	if !ok {
		basePath = "/var/lib/maas"
	}
	return filepath.Join(basePath, path)
}

func GetMAASID() (string, error) {
	maasIdLock.RLock()
	defer maasIdLock.RUnlock()

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
		maasIdLock.Lock()
		defer maasIdLock.Unlock()
		maasId = strings.TrimSpace(string(contents))
	}
	return maasId, nil
}

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
