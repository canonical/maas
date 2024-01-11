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

func TestBootloaderRegistryFindRemoteURL(t *testing.T) {
	table := map[string]struct {
		In  string
		Out string
		Err error
	}{
		"bootaa64.efi": {
			In:  "bootaa64.efi",
			Out: "/boot-resources/bootloaders/uefi/arm64/bootaa64.efi",
		},
		"grubaa64.efi": {
			In:  "grubaa64.efi",
			Out: "/boot-resources/bootloaders/uefi/arm64/grubaa64.efi",
		},
		"bootx64.efi": {
			In:  "bootx64.efi",
			Out: "/boot-resources/bootloaders/uefi/amd64/bootx64.efi",
		},
		"grubx64.efi": {
			In:  "grubx64.efi",
			Out: "/boot-resources/bootloaders/uefi/amd64/grubx64.efi",
		},
		"bootppc64.bin": {
			In:  "bootppc64.bin",
			Out: "/boot-resources/bootloaders/open-firmware/ppc64el/bootppc64.bin",
		},
		"lpxelinux.0": {
			In:  "lpxelinux.0",
			Out: "/boot-resources/bootloader/pxe/i386/lpxelinux.0",
		},
		"chain.c32": {
			In:  "chain.c32",
			Out: "/boot-resources/bootloader/pxe/i386/chain.c32",
		},
		"ifcpu.c32": {
			In:  "ifcpu.c32",
			Out: "/boot-resources/bootloader/pxe/i386/ifcpu.c32",
		},
		"ldlinux.c32": {
			In:  "ldlinux.c32",
			Out: "/boot-resources/bootloader/pxe/i386/ldlinux.c32",
		},
		"libcom32.c32": {
			In:  "libcom32.c32",
			Out: "/boot-resources/bootloader/pxe/i386/libcom32.c32",
		},
		"libutil.c32": {
			In:  "libutil.c32",
			Out: "/boot-resources/bootloader/pxe/i386/libutil.c32",
		},
		"does-not-exist": {
			In:  "does-not-exist.efi",
			Err: ErrInvalidBootloader,
		},
	}

	tmpDir, err := os.MkdirTemp("", "BootloaderRegistry.FindRemoteURL*")
	if err != nil {
		t.Fatal(err)
	}

	registry := NewBootloaderRegistry(nil, tmpDir)

	for tname, tcase := range table {
		t.Run(tname, func(tt *testing.T) {
			url, err := registry.FindRemoteURL(tcase.In)
			if err != nil {
				if tcase.Err != nil {
					assert.ErrorIs(tt, err, tcase.Err)
				} else {
					tt.Fatal(err)
				}
			}

			assert.Equal(tt, url, tcase.Out)
		})
	}
}
