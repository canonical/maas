package imagecache

import (
	"errors"
	"os"
	"path"
	"path/filepath"
	"strings"

	"github.com/rs/zerolog/log"
)

var (
	// ErrInvalidBootloader is an error for when a non-existent bootloader is requested
	ErrInvalidBootloader = errors.New("the requested bootloader was invaild")
)

var (
	srcDstPathMap = map[string]string{
		"/usr/lib/shim/shimx64.efi.signed":                      "bootx64.efi",
		"/usr/lib/grub/x86_64-efi-signed/grubnetx64.efi.signed": "grubx64.efi",
		"/usr/lib/PXELINUX/lpxelinux.0":                         "lpxelinux.0",
		"./lpxelinux.0":                                         "pxelinux.0",
		"/usr/lib/syslinux/modules/bios/chain.c32":              "chain.c32",
		"/usr/lib/syslinux/modules/bios/ifcpu64.c32":            "ifcpu64.c32",
		"/usr/lib/syslinux/modules/bios/ldlinux.c32":            "ldlinux.c32",
		"/usr/lib/syslinux/modules/bios/libcom32.c32":           "libcom32.c32",
		"/usr/lib/syslinux/modules/bios/libutil.c32":            "libutil.c32",
	}
	grubARMFiles = map[string]struct{}{
		"bootaa64.efi": {},
		"grubaa64.efi": {},
	}
	grubX64Files = map[string]struct{}{
		"bootx64.efi": {},
		"grubx64.efi": {},
	}
	ppcBootloaderFiles = map[string]struct{}{
		"bootppc64.bin": {},
	}
	pxeFiles = map[string]struct{}{
		"lpxelinux.0":  {},
		"chain.c32":    {},
		"ifcpu.c32":    {},
		"ldlinux.c32":  {},
		"libcom32.c32": {},
		"libutil.c32":  {},
	}
)

// BootloaderRegistry registers and holds links to each linked bootloader file
type BootloaderRegistry struct {
	bootloaders map[string]*BootloaderLinker
}

// NewBootloaderRegistry instantiates a new *BootloaderRegistry, and will optionally override the list of bootloader
// files and the location to which they are linked
func NewBootloaderRegistry(overrideSrcDstMap map[string]string, overrideCacheDir string) *BootloaderRegistry {
	pathMap := srcDstPathMap
	if overrideSrcDstMap != nil {
		pathMap = overrideSrcDstMap
	}

	cacheDir := ImageCacheDir
	if overrideCacheDir != "" {
		cacheDir = overrideCacheDir
	} else if os.Getenv("SNAP") != "" {
		cacheDir = path.Join(os.Getenv("SNAP_DATA"), cacheDir)
	}

	bootloaders := make(map[string]*BootloaderLinker)

	for src, dst := range pathMap {
		if !filepath.IsAbs(src) {
			src = path.Join(cacheDir, src)
		}

		bootloaders[dst] = NewBootloaderLinker(src, dst, bootloaders, cacheDir)
	}

	return &BootloaderRegistry{
		bootloaders: bootloaders,
	}
}

// LinkAll links all bootloader files
func (b *BootloaderRegistry) LinkAll() error {
	for _, linker := range b.bootloaders {
		err := linker.Link()
		if err != nil {
			log.Err(err).Msgf("unable to link %s", linker.dst)
		}
	}

	return nil
}

// IsBootloader checks if the requested file is a known bootloader file
func (b *BootloaderRegistry) IsBootloader(file string) bool {
	_, ok := b.bootloaders[file]
	return ok
}

// Find finds the requested file
func (b *BootloaderRegistry) Find(file string) (*os.File, bool, error) {
	linker, ok := b.bootloaders[file]
	if !ok {
		return nil, false, ErrInvalidBootloader
	}

	if !linker.linked {
		return nil, false, nil
	}

	f, err := linker.Open()
	if err != nil {
		return nil, false, err
	}

	return f, true, nil
}

// FindRemoteURL finds the remote URL for a bootloader file
func (b *BootloaderRegistry) FindRemoteURL(file string) (string, error) {
	linker, ok := b.bootloaders[file]
	if !ok {
		return "", ErrInvalidBootloader
	}

	return linker.RemotePath()
}

// BootloaderLinker is responsible for linking and reading
// a given bootloader file
type BootloaderLinker struct {
	name   string
	src    string
	dst    string
	linked bool
}

// NewBootloaderLinker instantiates a new *BootloaderLinker for the given src and dst mapping.
// It will return an existing *BootloaderLinker if one exists for the source file already to avoid nested linking
func NewBootloaderLinker(src, dst string, existing map[string]*BootloaderLinker, cacheDir string) *BootloaderLinker {
	srcSlice := strings.Split(src, "/")
	if ex, ok := existing[srcSlice[len(srcSlice)-1]]; ok {
		return ex
	}

	return &BootloaderLinker{
		name: dst,
		src:  src,
		dst:  path.Join(cacheDir, dst),
	}
}

// Link links the src file to dst if not already linked
func (b *BootloaderLinker) Link() error {
	if !b.linked {
		_, err := os.Stat(b.src)
		if err != nil {
			return err
		}

		err = os.Symlink(b.src, b.dst)
		if err != nil && !os.IsExist(err) {
			rmErr := os.Remove(b.dst)
			if rmErr != nil {
				log.Err(rmErr).Send()
			}

			return err
		}

		b.linked = true
	}

	return nil
}

// Open opens the src file, it follows the link rather than reading src directly,
// as the BootloaderLinker may have an existing link as a src
func (b *BootloaderLinker) Open() (*os.File, error) {
	link, err := os.Readlink(b.dst)
	if err != nil {
		return nil, err
	}

	//nolint:gosec // gosec wants a string literal, which doesn't work here
	return os.Open(link)
}

// RemotePath returns the path the file should be found at on the Region
// Controller
func (b *BootloaderLinker) RemotePath() (string, error) {
	var p string

	if _, ok := grubARMFiles[b.dst]; ok {
		p = path.Join("bootloaders/uefi/arm64/", b.name)
	} else if _, ok := grubX64Files[b.dst]; ok {
		p = path.Join("bootloaders/uefi/amd64/", b.name)
	} else if _, ok := ppcBootloaderFiles[b.dst]; ok {
		p = path.Join("bootloaders/open-firmware/ppc64el/", b.name)
	} else if _, ok := pxeFiles[b.dst]; ok {
		p = path.Join("bootloader/pxe/i386/", b.name)
	} else {
		return "", ErrInvalidBootloader
	}

	return path.Join("/boot-resources/", p), nil
}
