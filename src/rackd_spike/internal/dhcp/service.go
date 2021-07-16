package dhcp

import (
	"context"
	"errors"
	"net"

	"rackd/internal/service"
)

const (
	DhcpdSystemdUnitFile  = "maas-dhcpd.service"
	Dhcpd6SystemdUnitFile = "maas-dhcpd6.service"
)

var (
	ErrRackHasNoIPInSubnet = errors.New("this rack controller has no IP within the given subnet")
)

type DhcpService interface {
	service.Service
	Configure(context.Context, ConfigData, string) error
}

type ConfigData struct {
	TemplateData
	Interfaces []string
}

type DhcpdSystemdService struct {
	service.SystemdService
	configFileName string
}

func NewDhcpdSystemdService(ctx context.Context) (service.ReloadableService, error) {
	svc, err := service.NewSystemdService(ctx, "dhcpd", service.SvcDHCP, DhcpdSystemdUnitFile)
	if err != nil {
		return nil, err
	}
	unit, ok := svc.(*service.SystemdService)
	if !ok {
		return nil, service.ErrInvalidServiceType
	}
	return &DhcpdSystemdService{
		SystemdService: *unit,
		configFileName: DhcpdConfFileName,
	}, nil
}

func (d *DhcpdSystemdService) Configure(ctx context.Context, data ConfigData, _ string) error {
	err := RenderDhcpdConfToFile(data.TemplateData)
	if err != nil {
		return err
	}
	return d.Restart(ctx)
}

type Dhcpd6SystemdService struct {
	service.SystemdService
	configFileName string
}

func NewDhcpd6SystemdService(ctx context.Context) (service.ReloadableService, error) {
	svc, err := service.NewSystemdService(ctx, "dhcpd6", service.SvcDHCP6, Dhcpd6SystemdUnitFile)
	if err != nil {
		return nil, err
	}
	unit, ok := svc.(*service.SystemdService)
	if !ok {
		return nil, service.ErrInvalidServiceType
	}
	return &Dhcpd6SystemdService{
		SystemdService: *unit,
		configFileName: Dhcpd6ConfFileName,
	}, nil
}

func (d *Dhcpd6SystemdService) Configure(ctx context.Context, data ConfigData, _ string) error {
	err := RenderDhcpdConfToFile(data.TemplateData)
	if err != nil {
		return err
	}
	return d.Restart(ctx)
}

type DhcpdSupervisordService struct {
	service.SupervisordService
	configFileName string
}

func NewDhcpdSupervisordService(supervisorAddr string) (service.Service, error) {
	svc, err := service.NewSupervisordService(supervisorAddr, "dhcpd", service.SvcDHCP)
	if err != nil {
		return nil, err
	}
	supSvc, ok := svc.(*service.SupervisordService)
	if !ok {
		return nil, service.ErrInvalidServiceType
	}
	return &DhcpdSupervisordService{
		SupervisordService: *supSvc,
		configFileName:     DhcpdConfFileName,
	}, nil
}

func (d *DhcpdSupervisordService) Configure(ctx context.Context, data ConfigData, _ string) error {
	err := RenderDhcpdConfToFile(data.TemplateData)
	if err != nil {
		return err
	}
	return d.Restart(ctx)
}

type Dhcpd6SupervisordService struct {
	service.SupervisordService
	configFileName string
}

func NewDhcpd6SupervisordService(supervisorAddr string) (service.Service, error) {
	svc, err := service.NewSupervisordService(supervisorAddr, "dhcpd6", service.SvcDHCP6)
	if err != nil {
		return nil, err
	}
	supSvc, ok := svc.(*service.SupervisordService)
	if !ok {
		return nil, service.ErrInvalidServiceType
	}
	return &Dhcpd6SupervisordService{
		SupervisordService: *supSvc,
		configFileName:     Dhcpd6ConfFileName,
	}, nil
}

func (d *Dhcpd6SupervisordService) Configure(ctx context.Context, data ConfigData, _ string) error {
	err := RenderDhcpd6ConfToFile(data.TemplateData)
	if err != nil {
		return err
	}
	return d.Restart(ctx)
}

func GetRackIP(subnet string) (string, error) {
	_, sn, err := net.ParseCIDR(subnet)
	if err != nil {
		return "", err
	}
	ifaces, err := net.Interfaces()
	if err != nil {
		return "", err
	}
	for _, iface := range ifaces {
		addrs, err := iface.Addrs()
		if err != nil {
			return "", err
		}
		for _, addr := range addrs {
			ifaceIP := net.ParseIP(addr.String())
			if sn.Contains(ifaceIP) {
				return addr.String(), nil
			}
		}
	}
	return "", ErrRackHasNoIPInSubnet
}
