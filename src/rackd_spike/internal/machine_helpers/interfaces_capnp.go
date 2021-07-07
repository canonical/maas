package machinehelpers

import (
	"rackd/pkg/rpc"
)

type CapnpInterfaces map[string]Interface

func (c CapnpInterfaces) SetProto(ifacePayload rpc.Interfaces) error {
	ifaces, err := ifacePayload.NewIfaces(int32(len(c)))
	if err != nil {
		return err
	}
	var idx int
	for name, iface := range c {
		protoIface := ifaces.At(idx)
		err = protoIface.SetName(name)
		if err != nil {
			return err
		}
		details, err := protoIface.NewIface()
		if err != nil {
			return err
		}
		details.SetMacAddress(iface.Mac)
		details.SetType(iface.Type)
		protoLinks, err := details.NewLinks(int32(len(iface.Links)))
		if err != nil {
			return err
		}
		for i, link := range iface.Links {
			protoLink := protoLinks.At(i)
			err = protoLink.SetMode(link.Mode)
			if err != nil {
				return err
			}
			err = protoLink.SetAddress(link.Address)
			if err != nil {
				return err
			}
			err = protoLink.SetGateway(link.Gateway)
			if err != nil {
				return err
			}
			protoLink.SetNetmask(int32(link.Netmask))
		}
		if iface.Vlan != nil {
			details.SetVid(iface.Vlan.Vid)
		}
		if len(iface.Parents) > 0 {
			protoParents, err := details.NewParents(int32(len(iface.Parents)))
			if err != nil {
				return err
			}
			for i, parent := range iface.Parents {
				err = protoParents.Set(i, parent)
				if err != nil {
					return err
				}
			}
		}
		idx++
	}
	return nil
}
