from enum import Enum


class PowerTypeEnum(str, Enum):
    AMT = "amt"
    APC = "apc"
    HMC = "hmc"
    HMCZ = "hmcz"
    IPMI = "ipmi"
    LXD = "lxd"
    MANUAL = "manual"
    MOONSHOT = "moonshot"
    PROXMOX = "proxmox"
    RARITAN = "raritan"
    RECS = "recs_box"
    REDFISH = "redfish"
    SEAMICRO = "sm15k"
    VIRSH = "virsh"
    VMWARE = "vmware"
    WEBHOOK = "webhook"

    def __str__(self):
        return str(self.value)
