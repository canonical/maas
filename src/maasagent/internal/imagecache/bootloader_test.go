package imagecache

import (
	"fmt"
	"os"
	"path"
	"strings"
	"testing"

	"github.com/stretchr/testify/assert"
)

func TestBootloaderRegistryLinkAll(t *testing.T) {
	table := map[string]struct {
		CreateIn func() (map[string]string, string, error)
		NotFound bool
	}{
		"basic_files": {
			CreateIn: func() (map[string]string, string, error) {
				files := make(map[string]string)

				dir, err := os.MkdirTemp("", "bootloader_registry_link_basic_files*")
				if err != nil {
					return nil, "", err
				}

				for i := 0; i < 5; i++ {
					f, err := os.CreateTemp(dir, "test.file*.txt")
					if err != nil {
						return nil, "", err
					}

					nameSlice := strings.Split(f.Name(), ".")

					files[f.Name()] = fmt.Sprintf("dst.%s.txt", nameSlice[1])

					err = f.Close()
					if err != nil {
						return nil, "", err
					}
				}

				return files, dir, nil
			},
		},
		"missing_files": {
			CreateIn: func() (map[string]string, string, error) {
				files := make(map[string]string)

				dir, err := os.MkdirTemp(os.TempDir(), "bootloader_registry_link_missing_files*")
				if err != nil {
					return nil, "", err
				}

				for i := 0; i < 5; i++ {
					files[path.Join(dir, fmt.Sprintf("test.%d.txt", i))] = fmt.Sprintf("dst.%d.txt", i)
				}

				return files, dir, nil
			},
			NotFound: true,
		},
	}

	for tname, tcase := range table {
		in, dir, err := tcase.CreateIn()
		if err != nil {
			t.Fatal(err)
		}

		t.Run(tname, func(tt *testing.T) {
			registry := NewBootloaderRegistry(in, dir)

			err := registry.LinkAll()
			if err != nil {
				tt.Error(err)
			}

			for src, dst := range in {
				link, err := os.Readlink(path.Join(dir, dst))
				if err != nil {
					if tcase.NotFound {
						assert.True(tt, os.IsNotExist(err), err)
						continue
					}
					tt.Error(err)
				}

				assert.Equal(tt, src, link)
			}
		})
	}
}
