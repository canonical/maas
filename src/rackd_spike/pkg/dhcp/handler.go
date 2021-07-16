package dhcp

import (
	"context"
	"net"

	internal "rackd/internal/dhcp"
	"rackd/internal/service"
	"rackd/pkg/rpc"
)

type Handler struct {
	sup      service.SvcManager
	dhcp4Svc internal.DhcpService
	dhcp6Svc internal.DhcpService
}

func NewHandler(proxy bool, sup service.SvcManager) (*Handler, error) {
	h := &Handler{
		sup: sup,
	}
	if !proxy {
		dhcp4, err := sup.GetByType(service.SvcDHCP)
		if err != nil {
			return nil, err
		}
		h.dhcp4Svc = dhcp4[0].(internal.DhcpService)
		dhcp6, err := sup.GetByType(service.SvcDHCP6)
		if err != nil {
			return nil, err
		}
		h.dhcp6Svc = dhcp6[0].(internal.DhcpService)
	} else {
		relay, err := sup.GetByType(service.SvcDHCPRelay)
		if err != nil {
			return nil, err
		}
		h.dhcp4Svc = relay[0].(internal.DhcpService)
		h.dhcp6Svc = h.dhcp4Svc
	}
	return h, nil
}

func rpcDataToConfig(data rpc.ConfigureDHCPReq) (res internal.ConfigData, err error) {
	rpcSharedNetworks, err := data.SharedNetworks()
	if err != nil {
		return res, err
	}
	rpcHosts, err := data.Hosts()
	if err != nil {
		return res, err
	}
	rpcFailoverPeers, err := data.FailoverPeers()
	if err != nil {
		return res, err
	}
	rpcInterfaces, err := data.Interfaces()
	if err != nil {
		return res, err
	}
	res = internal.ConfigData{
		TemplateData: internal.TemplateData{
			DHCPSocket:     internal.DefaultDHCPSocket,
			DHCPHelper:     internal.DefaultDHCPHelper,
			SharedNetworks: make([]internal.SharedNetwork, rpcSharedNetworks.Len()),
			Hosts:          make([]internal.Host, rpcHosts.Len()),
			FailoverPeers:  make([]internal.FailoverPeer, rpcFailoverPeers.Len()),
		},
		Interfaces: make([]string, rpcInterfaces.Len()),
	}
	res.OMAPIKey, err = data.OmapiKey()
	if err != nil {
		return res, err
	}
	for i := 0; i < rpcInterfaces.Len(); i++ {
		res.Interfaces[i], err = rpcInterfaces.At(i)
		if err != nil {
			return res, err
		}
	}
	for i := 0; i < rpcHosts.Len(); i++ {
		host := rpcHosts.At(i)
		snippets, err := host.DhcpSnippets()
		if err != nil {
			return res, err
		}
		res.Hosts[i].Host, err = host.Host()
		if err != nil {
			return res, err
		}
		res.Hosts[i].MAC, err = host.Mac()
		if err != nil {
			return res, err
		}
		res.Hosts[i].IP, err = host.Ip()
		if err != nil {
			return res, err
		}
		res.Hosts[i].DHCPSnippets = make([]internal.DhcpSnippet, snippets.Len())
		for j := 0; j < snippets.Len(); j++ {
			snippet := snippets.At(j)
			res.Hosts[i].DHCPSnippets[j].Name, err = snippet.Name()
			if err != nil {
				return res, err
			}
			res.Hosts[i].DHCPSnippets[j].Description, err = snippet.Description()
			if err != nil {
				return res, err
			}
			res.Hosts[i].DHCPSnippets[j].Value, err = snippet.Value()
			if err != nil {
				return res, err
			}
		}
	}
	for i := 0; i < rpcSharedNetworks.Len(); i++ {
		sharedNet := rpcSharedNetworks.At(i)
		res.SharedNetworks[i].Name, err = sharedNet.Name()
		subnets, err := sharedNet.Subnets()
		if err != nil {
			return res, err
		}
		res.SharedNetworks[i].Subnets = make([]internal.Subnet, subnets.Len())
		for j := 0; j < subnets.Len(); j++ {
			subnet := subnets.At(j)
			val, err := subnet.Subnet()
			if err != nil {
				return res, err
			}
			res.SharedNetworks[i].Subnets[j].Subnet = val
			res.SharedNetworks[i].Subnets[j].SubnetMask, err = subnet.SubnetMask()
			if err != nil {
				return res, err
			}
			res.SharedNetworks[i].Subnets[j].CIDR, err = subnet.SubnetCIDR()
			if err != nil {
				return res, err
			}
			res.SharedNetworks[i].Subnets[j].NextServer, err = internal.GetRackIP(val)
			if err != nil {
				return res, err
			}
			res.SharedNetworks[i].Subnets[j].BroadcastIP, err = subnet.BroadcastIP()
			if err != nil {
				return res, err
			}
			dnsServers, err := subnet.DnsServers()
			if err != nil {
				return res, err
			}
			res.SharedNetworks[i].Subnets[j].DNSServers = make([]string, dnsServers.Len())
			for k := 0; k < dnsServers.Len(); k++ {
				res.SharedNetworks[i].Subnets[j].DNSServers[k], err = dnsServers.At(k)
				if err != nil {
					return res, err
				}
			}
			res.SharedNetworks[i].Subnets[j].DomainName, err = subnet.DomainName()
			if err != nil {
				return res, err
			}
			searchList, err := subnet.SearchList()
			if err != nil {
				return res, err
			}
			res.SharedNetworks[i].Subnets[j].SearchList = make([]string, searchList.Len())
			for k := 0; k < searchList.Len(); k++ {
				res.SharedNetworks[i].Subnets[j].SearchList[k], err = searchList.At(k)
				if err != nil {
					return res, err
				}
			}
			res.SharedNetworks[i].Subnets[j].RouterIP, err = subnet.RouterIP()
			if err != nil {
				return res, err
			}
			ntpServers, err := subnet.NtpServers()
			if err != nil {
				return res, err
			}
			for k := 0; k < ntpServers.Len(); k++ {
				ntpServer, err := ntpServers.At(k)
				if err != nil {
					return res, err
				}
				ntpIP := net.ParseIP(ntpServer)
				if ntpIP.To4() != nil {
					res.SharedNetworks[i].Subnets[j].NTPServersIPv4 = ntpServer
				} else {
					res.SharedNetworks[i].Subnets[j].NTPServersIPv6 = ntpServer
				}
			}
			res.SharedNetworks[i].Subnets[j].MTU = int(sharedNet.Mtu())
			if err != nil {
				return res, err
			}
			disabledBootArchitectures, err := subnet.DisabledBootArchitectures()
			if err != nil {
				return res, err
			}
			bootloaderData := internal.ConditionalBootloaderData{
				IPv6:                      len(res.SharedNetworks[i].Subnets[j].CIDR) > 0,
				RackIP:                    res.SharedNetworks[i].Subnets[j].NextServer,
				DisabledBootArchitectures: make([]string, disabledBootArchitectures.Len()),
			}
			for k := 0; k < disabledBootArchitectures.Len(); k++ {
				bootloaderData.DisabledBootArchitectures[k], err = disabledBootArchitectures.At(k)
				if err != nil {
					return res, err
				}
			}
			res.SharedNetworks[i].Subnets[j].Bootloader, err = internal.ComposeConditionalBootloader(bootloaderData)
			if err != nil {
				return res, err
			}
			snippets, err := subnet.DhcpSnippets()
			if err != nil {
				return res, err
			}
			pools, err := subnet.Pools()
			if err != nil {
				return res, err
			}
			res.SharedNetworks[i].Subnets[j].DHCPSnippets = make([]internal.DhcpSnippet, snippets.Len())
			res.SharedNetworks[i].Subnets[j].Pools = make([]internal.Pool, pools.Len())
			for k := 0; k < snippets.Len(); k++ {
				snippet := snippets.At(k)
				res.SharedNetworks[i].Subnets[j].DHCPSnippets[k].Name, err = snippet.Name()
				if err != nil {
					return res, err
				}
				res.SharedNetworks[i].Subnets[j].DHCPSnippets[k].Description, err = snippet.Description()
				if err != nil {
					return res, err
				}
				res.SharedNetworks[i].Subnets[j].DHCPSnippets[k].Value, err = snippet.Value()
				if err != nil {
					return res, err
				}
			}
			for k := 0; k < pools.Len(); k++ {
				pool := pools.At(k)
				res.SharedNetworks[i].Subnets[j].Pools[k].FailoverPeer, err = pool.FailoverPeer()
				if err != nil {
					return res, err
				}
				res.SharedNetworks[i].Subnets[j].Pools[k].IPRangeLow, err = pool.IpRangeLow()
				if err != nil {
					return res, err
				}
				res.SharedNetworks[i].Subnets[j].Pools[k].IPRangeHigh, err = pool.IpRangeHigh()
				if err != nil {
					return res, err
				}
				snippets, err := pool.DhcpSnippets()
				if err != nil {
					return res, err
				}
				res.SharedNetworks[i].Subnets[j].Pools[k].DHCPSnippets = make([]internal.DhcpSnippet, snippets.Len())
				for m := 0; m < snippets.Len(); m++ {
					snippet := snippets.At(m)
					res.SharedNetworks[i].Subnets[j].Pools[k].DHCPSnippets[m].Name, err = snippet.Name()
					if err != nil {
						return res, err
					}
					res.SharedNetworks[i].Subnets[j].Pools[k].DHCPSnippets[m].Description, err = snippet.Description()
					if err != nil {
						return res, err
					}
					res.SharedNetworks[i].Subnets[j].Pools[k].DHCPSnippets[m].Value, err = snippet.Value()
					if err != nil {
						return res, err
					}
				}
			}
		}
	}
	for i := 0; i < rpcFailoverPeers.Len(); i++ {
		failoverPeer := rpcFailoverPeers.At(i)
		res.FailoverPeers[i].Name, err = failoverPeer.Name()
		if err != nil {
			return res, err
		}
		res.FailoverPeers[i].Mode, err = failoverPeer.Mode()
		if err != nil {
			return res, err
		}
		res.FailoverPeers[i].Address, err = failoverPeer.Address()
		if err != nil {
			return res, err
		}
		res.FailoverPeers[i].PeerAddress, err = failoverPeer.PeerAddress()
		if err != nil {
			return res, err
		}
	}
	return res, nil
}

func (h *Handler) ConfigureDHCPv4(ctx context.Context, data rpc.RegionController_RackController_configureDHCPv4, regionIP string) error {
	args, err := data.Args().Req()
	if err != nil {
		return err
	}
	cData, err := rpcDataToConfig(args)
	if err != nil {
		return err
	}
	return h.dhcp4Svc.Configure(ctx, cData, regionIP)
}

func (h *Handler) ConfigureDHCPv6(ctx context.Context, data rpc.RegionController_RackController_configureDHCPv6, regionIP string) error {
	args, err := data.Args().Req()
	if err != nil {
		return err
	}
	cData, err := rpcDataToConfig(args)
	if err != nil {
		return err
	}
	return h.dhcp6Svc.Configure(ctx, cData, regionIP)
}
