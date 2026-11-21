#!/usr/bin/python3
# Copyright 2020 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).
#
# hdparm / nvme-cli outputs used on maas_wipe testing

HDPARM_BEFORE_SECURITY = b"""\
/dev/sda:

ATA device, with non-removable media
    Model Number:       INTEL SSDSC2CT240A4
    Serial Number:      CVKI3206029X240DGN
    Firmware Revision:  335u
    Transport:          Serial, ATA8-AST, SATA 1.0a, SATA II Extensions
Standards:
    Used: unknown (minor revision code 0xffff)
    Supported: 9 8 7 6 5
    Likely used: 9
Configuration:
    Logical		max	current
    cylinders	16383	16383
    heads		16	16
    sectors/track	63	63
    --
    CHS current addressable sectors:   16514064
    LBA    user addressable sectors:  268435455
    LBA48  user addressable sectors:  468862128
    Logical  Sector size:                   512 bytes
    Physical Sector size:                   512 bytes
    Logical Sector-0 offset:                  0 bytes
    device size with M = 1024*1024:      228936 MBytes
    device size with M = 1000*1000:      240057 MBytes (240 GB)
    cache/buffer size  = unknown
    Nominal Media Rotation Rate: Solid State Device
Capabilities:
    LBA, IORDY(can be disabled)
    Queue depth: 32
    Standby timer values: spec'd by Standard, no device specific minimum
    R/W multiple sector transfer: Max = 16	Current = 16
    Advanced power management level: 254
    DMA: mdma0 mdma1 mdma2 udma0 udma1 udma2 udma3 udma4 udma5 *udma6
         Cycle time: min=120ns recommended=120ns
    PIO: pio0 pio1 pio2 pio3 pio4
         Cycle time: no flow control=120ns  IORDY flow control=120ns
Commands/features:
    Enabled	Supported:
       *	SMART feature set
            Security Mode feature set
       *	Power Management feature set
       *	Write cache
       *	Look-ahead
       *	Host Protected Area feature set
       *	WRITE_BUFFER command
       *	READ_BUFFER command
       *	NOP cmd
       *	DOWNLOAD_MICROCODE
       *	Advanced Power Management feature set
            Power-Up In Standby feature set
       *	48-bit Address feature set
       *	Mandatory FLUSH_CACHE
       *	FLUSH_CACHE_EXT
       *	SMART error logging
       *	SMART self-test
       *	General Purpose Logging feature set
       *	WRITE_{DMA|MULTIPLE}_FUA_EXT
       *	64-bit World wide name
       *	IDLE_IMMEDIATE with UNLOAD
       *	WRITE_UNCORRECTABLE_EXT command
       *	{READ,WRITE}_DMA_EXT_GPL commands
       *	Segmented DOWNLOAD_MICROCODE
       *	Gen1 signaling speed (1.5Gb/s)
       *	Gen2 signaling speed (3.0Gb/s)
       *	Gen3 signaling speed (6.0Gb/s)
       *	Native Command Queueing (NCQ)
       *	Host-initiated interface power management
       *	Phy event counters
       *	DMA Setup Auto-Activate optimization
            Device-initiated interface power management
       *	Software settings preservation
       *	SMART Command Transport (SCT) feature set
       *	SCT Data Tables (AC5)
       *	reserved 69[4]
       *	Data Set Management TRIM supported (limit 1 block)
       *	Deterministic read data after TRIM
"""

HDPARM_AFTER_SECURITY = b"""\
Logical Unit WWN Device Identifier: 55cd2e40002643cf
    NAA		: 5
    IEEE OUI	: 5cd2e4
    Unique ID	: 0002643cf
Checksum: correct
"""

HDPARM_SECURITY_NOT_SUPPORTED = b"""\
Security:
    Master password revision code = 65534
    not supported
    not enabled
    not locked
    not frozen
    not	expired: security count
        supported: enhanced erase
    4min for SECURITY ERASE UNIT. 2min for ENHANCED SECURITY ERASE UNIT.
"""

HDPARM_SECURITY_SUPPORTED_NOT_ENABLED = b"""\
Security:
    Master password revision code = 65534
        supported
    not enabled
    not locked
    not frozen
    not	expired: security count
        supported: enhanced erase
    4min for SECURITY ERASE UNIT. 2min for ENHANCED SECURITY ERASE UNIT.
"""

HDPARM_SECURITY_SUPPORTED_ENABLED = b"""\
Security:
    Master password revision code = 65534
        supported
        enabled
    not locked
    not frozen
    not	expired: security count
        supported: enhanced erase
    4min for SECURITY ERASE UNIT. 2min for ENHANCED SECURITY ERASE UNIT.
"""

HDPARM_SECURITY_ALL_TRUE = b"""\
Security:
    Master password revision code = 65534
        supported
        enabled
        locked
        frozen
    not	expired: security count
        supported: enhanced erase
    4min for SECURITY ERASE UNIT. 2min for ENHANCED SECURITY ERASE UNIT.
"""

NVME_IDCTRL_PROLOGUE = b"""\
NVME Identify Controller:
vid     : 0x8086
ssvid   : 0x8086
sn      : CVMD5066002T400AGN
mn      : INTEL SSDPEDME400G4
fr      : 8DV10131
rab     : 0
ieee    : 5cd2e4
cmic    : 0
mdts    : 5
cntlid  : 0
ver     : 0
rtd3r   : 0
rtd3e   : 0
oaes    : 0
ctratt  : 0
acl     : 3
aerl    : 3
frmw    : 0x2
lpa     : 0
elpe    : 63
npss    : 0
avscc   : 0
apsta   : 0
wctemp  : 0
cctemp  : 0
mtfa    : 0
hmpre   : 0
hmmin   : 0
tnvmcap : 0
unvmcap : 0
rpmbs   : 0
edstt   : 0
dsto    : 0
fwug    : 0
kas     : 0
hctma   : 0
mntmt   : 0
mxtmt   : 0
sanicap : 0
hmminds : 0
hmmaxd  : 0
sqes    : 0x66
cqes    : 0x44
maxcmd  : 0
nn      : 1
fuses   : 0
"""

NVME_IDCTRL_OACS_FORMAT_SUPPORTED = b"""\
oacs    : 0x6
"""

NVME_IDCTRL_OACS_FORMAT_UNSUPPORTED = b"""\
oacs    : 0x4
"""

NVME_IDCTRL_ONCS_WRITEZ_SUPPORTED = b"""\
oncs    : 0xe
"""

NVME_IDCTRL_ONCS_WRITEZ_UNSUPPORTED = b"""\
oncs    : 0x6
"""

NVME_IDCTRL_FNA_CRYPTFORMAT_SUPPORTED = b"""\
fna     : 0x7
"""

NVME_IDCTRL_FNA_CRYPTFORMAT_UNSUPPORTED = b"""\
fna     : 0x3
"""

NVME_IDCTRL_EPILOGUE = b"""\
vwc     : 0
awun    : 0
awupf   : 0
nvscc   : 0
acwu    : 0
sgls    : 0
subnqn  :
ioccsz  : 0
iorcsz  : 0
icdoff  : 0
ctrattr : 0
msdbd   : 0
ps    0 : mp:25.00W operational enlat:0 exlat:0 rrt:0 rrl:0
          rwt:0 rwl:0 idle_power:- active_power:-
"""
