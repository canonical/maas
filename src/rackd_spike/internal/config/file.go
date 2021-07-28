package config

import (
	"os"
	"strings"
	"sync"
)

var (
	lock  sync.Mutex
	cache map[ConfigKey]string = make(map[ConfigKey]string)
)

func getConfigFromFile(id ConfigKey) (string, error) {
	lock.Lock()
	defer lock.Unlock()

	val, ok := cache[id]
	if !ok {
		path := getAbsPath(string(id))
		contents, err := os.ReadFile(path)
		if err != nil {
			if os.IsNotExist(err) {
				return "", nil
			}
			return "", err
		}

		val = strings.TrimSpace(string(contents))
		cache[id] = val
	}

	return val, nil
}

func setConfigToFile(id ConfigKey, value string) error {
	lock.Lock()
	defer lock.Unlock()

	value = strings.TrimSpace(value)

	path := getAbsPath(string(id))
	err := os.WriteFile(path, []byte(value), 0640)
	if err != nil {
		return err
	}

	cache[id] = value
	return nil
}
