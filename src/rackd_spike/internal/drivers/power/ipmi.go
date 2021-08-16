package power

import (
	"context"
	"net"

	"rackd/internal/drivers"
	"rackd/internal/drivers/power/ipmi"
	machinehelpers "rackd/internal/machine_helpers"
)

const (
	IPMIDriverLan  = "LAN"
	IPMIDriverLan2 = "LAN_2_0"

	IPMIBootTypeDefault = "auto"
	IPMIBootTypeLegacy  = "legacy"
	IPMIBootTypeEFI     = "efi"

	IPMIPrivilegeLevelUser     = "USER"
	IPMIPrivilegeLevelOperator = "OPERATOR"
	IPMIPrivilegeLevelAdmin    = "ADMIN"
)

var (
	IPMIWaitTime = [4]int{4, 8, 16, 32}

	IPMIDriverChoices = map[string]string{
		IPMIDriverLan:  "LAN [IPMI 1.5]",
		IPMIDriverLan2: "LAN_2_0 [IPMI 2.0]",
	}

	IPMIBootTypeChoices = map[string]string{
		IPMIBootTypeDefault: "Automatic",
		IPMIBootTypeLegacy:  "Legacy boot",
		IPMIBootTypeEFI:     "EFI boot",
	}

	IPMIBootTypeMapping = map[string]string{
		IPMIBootTypeEFI:    "EFI",
		IPMIBootTypeLegacy: "PC-COMPATIBLE",
	}

	IPMICipherSuiteIDChoices = map[string]string{
		"":   "freeipmi-tools default",
		"17": "17 - HMAC-SHA256::HMAC_SHA256_128::AES-CBC-128",
		"3":  "3 - HMAC-SHA1::HMAC-SHA1-96::AES-CBC-128",
		"8":  "8 - HMAC-MD5::HMAC-MD5-128::AES-CBC-128",
		"12": "12 - HMAC-MD5::MD5-128::AES-CBC-128",
	}

	IPMIPrivilegeLevelChoices = map[string]string{
		IPMIPrivilegeLevelUser:     "User",
		IPMIPrivilegeLevelOperator: "Operator",
		IPMIPrivilegeLevelAdmin:    "Administrator",
	}
)

type IPMIDriver struct {
	settings *PowerConfig
}

func NewIPMIDriver() *IPMIDriver {
	settings := &PowerConfig{}
	err := settings.CreateField("power_driver", ConfigTypeChoice, true,
		OptionalFieldAttrs{Default: IPMIDriverLan, Choices: IPMIDriverChoices})
	if err != nil {
		panic(err) // All these errors should be the result of something defined at compile-time, so better to error hard
	}
	err = settings.CreateField("power_boot_type", ConfigTypeChoice, false,
		OptionalFieldAttrs{Default: IPMIBootTypeDefault, Choices: IPMIBootTypeChoices})
	if err != nil {
		panic(err)
	}
	err = settings.CreateField("mac_address", ConfigTypeMACAddress, true)
	if err != nil {
		panic(err)
	}
	err = settings.CreateField("power_address", ConfigTypeMACAddress, false)
	if err != nil {
		panic(err)
	}
	err = settings.CreateField("power_user", ConfigTypeString, false)
	if err != nil {
		panic(err)
	}
	err = settings.CreateField("power_pass", ConfigTypePassword, false)
	if err != nil {
		panic(err)
	}
	err = settings.CreateField("k_g", ConfigTypePassword, false)
	if err != nil {
		panic(err)
	}
	err = settings.CreateField("cipher_suite_id", ConfigTypeChoice, false,
		OptionalFieldAttrs{Default: "3", Choices: IPMICipherSuiteIDChoices})
	if err != nil {
		panic(err)
	}
	err = settings.CreateField("privilege_level", ConfigTypeChoice, false,
		OptionalFieldAttrs{Default: IPMIPrivilegeLevelOperator, Choices: IPMIPrivilegeLevelChoices})
	if err != nil {
		panic(err)
	}
	return &IPMIDriver{
		settings: settings,
	}
}

func (i *IPMIDriver) Name() string {
	return "ipmi"
}

func (i *IPMIDriver) Description() string {
	return "IPMI"
}

func (i *IPMIDriver) Settings() *PowerConfig {
	return i.settings
}

func (i *IPMIDriver) IPExtractor() drivers.IPExtractor {
	return drivers.NewIPExtractor("power_address", drivers.IPExtractorIdentity)
}

func (i *IPMIDriver) Queryable() bool {
	return false
}

func (i *IPMIDriver) Chassis() bool {
	return false
}

func (i *IPMIDriver) CanProbe() bool {
	return false
}

func (i *IPMIDriver) CanSetBootOrder() bool {
	return false
}

func (i *IPMIDriver) DetectMissingPackages() error {
	return nil
}

func (i *IPMIDriver) Schema() map[string]interface{} {
	return nil
}

func (i *IPMIDriver) GetSetting(field string) (string, error) {
	return "", nil
}

func (i *IPMIDriver) connFromCfg(ctx context.Context, cfg *PowerConfig) (*ipmi.LanConn, error) {
	remoteIPStr, err := cfg.Get("power_address")
	if err != nil {
		return nil, err
	}

	var remoteIP net.IP
	if len(remoteIPStr) == 0 {
		mac, err := cfg.GetMAC("mac_address")
		if err != nil {
			return nil, err
		}
		remoteIP, err = machinehelpers.FindIPByArp(ctx, mac)
		if err != nil {
			return nil, err
		}
	}
	user, err := cfg.Get("power_user")
	if err != nil {
		return nil, err
	}
	password, err := cfg.Get("power_pass")
	if err != nil {
		return nil, err
	}
	privLvl, err := cfg.GetChoice("privilege_level")
	if err != nil {
		return nil, err
	}
	info := ipmi.ConnInfo{
		Port:     623,
		IP:       remoteIP.String(),
		BindAddr: "0.0.0.0",
		Username: user,
		Password: password,
		PrivLvl:  privLvl,
	}
	return ipmi.NewLanConn(info), nil
}

func (i *IPMIDriver) applyConfig(conn *ipmi.LanConn, cfg *PowerConfig) error {
	err := conn.SetBootDevice(ipmi.IPMIBootDevicePxe)
	if err != nil {
		return err
	}
	return nil
}

func (i *IPMIDriver) PowerOn(ctx context.Context, systemID string, cfg *PowerConfig) error {
	conn, err := i.connFromCfg(ctx, cfg)
	if err != nil {
		return err
	}
	err = conn.Open()
	if err != nil {
		return err
	}
	defer conn.Close()
	err = conn.StartSession()
	if err != nil {
		return err
	}
	defer conn.EndSession()
	err = i.applyConfig(conn, cfg)
	if err != nil {
		return err
	}
	return conn.PowerCtrl(ipmi.IPMIPowerStateOn)
}

func (i *IPMIDriver) PowerOff(ctx context.Context, systemID string, cfg *PowerConfig) error {
	conn, err := i.connFromCfg(ctx, cfg)
	if err != nil {
		return err
	}
	err = conn.Open()
	if err != nil {
		return err
	}
	defer conn.Close()
	err = conn.StartSession()
	if err != nil {
		return err
	}
	defer conn.EndSession()
	err = i.applyConfig(conn, cfg)
	if err != nil {
		return err
	}
	return conn.PowerCtrl(ipmi.IPMIPowerStateOff)
}

func (i *IPMIDriver) PowerQuery(ctx context.Context, systemID string, cfg *PowerConfig) error {
	return nil
}
