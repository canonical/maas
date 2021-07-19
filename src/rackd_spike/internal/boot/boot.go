package boot

var (
	BootMethodRegistry = map[string]BootMethod{
		"ipxe": {
			Name:                  "ipxe",
			UserClass:             "iPXE",
			PathPrefixHTTP:        true,
			AbsoluteURLAsFileName: true,
			BootloaderPath:        "ipxe.cfg",
		},
		"uefi_amd64_tftp": {
			Name:           "uefi_amd64_tftp",
			ArchOctet:      "00:07",
			BootloaderPath: "bootx64.efi",
		},
		"uefi_amd64_http": {
			Name:                  "uefi_amd64_http",
			ArchOctet:             "00:10",
			AbsoluteURLAsFileName: true,
			HTTPURL:               true,
			BootloaderPath:        "bootx64.efi",
		},
		"uefi_ebc_tftp": {
			Name:           "uefi_ebc_tftp",
			BootloaderPath: "bootx64.efi",
			ArchOctet:      "00:09",
		},
		"uefi_arm64_tftp": {
			Name:           "uefi_arm64_tftp",
			BootloaderPath: "bootaa64.efi",
			ArchOctet:      "00:0B",
		},
		"uefi_arm64_http": {
			Name:                  "uefi_arm64_http",
			BootloaderPath:        "bootaa64.efi",
			ArchOctet:             "00:13",
			AbsoluteURLAsFileName: true,
			HTTPURL:               true,
		},
		"open-firmware-ppc64el": {
			Name:           "open-firmware-ppc64el",
			BootloaderPath: "bootppc64.bin",
			ArchOctet:      "00:0C",
		},
		"powernv": {
			Name:           "powernv",
			ArchOctet:      "00:0E",
			BootloaderPath: "pxelinux.0",
			PathPrefix:     "ppc64el/",
		},
		"pxe": {
			Name:            "pxe",
			ArchOctet:       "00:00",
			BootloaderPath:  "lpxelinux.0",
			PathPrefixHTTP:  true,
			PathPrefixForce: true,
		},
		"s390x": {
			Name:           "s390x",
			BootloaderPath: "boots390x.bin",
			ArchOctet:      "00:1F",
			PathPrefix:     "s390x/",
		},
		"s390x_partition": {
			Name:           "s390x_partition",
			BootloaderPath: "s390x_partition/maas",
			ArchOctet:      "00:20",
		},
		"windows": {
			Name:           "windows",
			BootloaderPath: "pxeboot.0",
		},
	}
)

type BootMethod struct {
	PathPrefixHTTP        bool
	HTTPURL               bool
	PathPrefix            string
	BootloaderPath        string
	AbsoluteURLAsFileName bool
	ArchOctet             string
	UserClass             string
	PathPrefixForce       bool
	Name                  string
}
