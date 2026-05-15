export enum BondLacpRate {
  SLOW = "slow",
  FAST = "fast",
}

export enum BondMode {
  BALANCE_RR = "balance-rr",
  ACTIVE_BACKUP = "active-backup",
  BALANCE_XOR = "balance-xor",
  BROADCAST = "broadcast",
  LINK_AGGREGATION = "802.3ad",
  BALANCE_TLB = "balance-tlb",
  BALANCE_ALB = "balance-alb",
}

export enum BondXmitHashPolicy {
  ENCAP2_3 = "encap2+3",
  ENCAP3_4 = "encap3+4",
  LAYER2 = "layer2",
  LAYER2_3 = "layer2+3",
  LAYER3_4 = "layer3+4",
}

export enum BootProtocol {
  HTTP = "http",
  TFTP = "tftp",
}

export enum DriverType {
  POD = "pod",
  POWER = "power",
}

export enum GeneralMeta {
  MODEL = "general",
}

export enum PowerFieldScope {
  BMC = "bmc",
  NODE = "node",
}

export enum PowerFieldType {
  CHOICE = "choice",
  MAC_ADDRESS = "mac_address",
  MULTIPLE_CHOICE = "multiple_choice",
  PASSWORD = "password",
  STRING = "string",
  IP_ADDRESS = "ip_address",
  VIRSH_ADDRESS = "virsh_address",
  LXD_ADDRESS = "lxd_address",
}
