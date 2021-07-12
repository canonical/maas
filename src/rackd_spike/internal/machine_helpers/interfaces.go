package machinehelpers

import (
	"bufio"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"sort"
	"strconv"
	"strings"

	lxdresources "github.com/lxc/lxd/shared/api"
)

var (
	excludedInterfaceTypes = map[string]struct{}{
		"loopback": {},
		"ipip":     {},
		"tunnel":   {},
	}

	leaseRx = regexp.MustCompile(`(?m)(^\s*lease\s+{([^}]+)})`)
)

// isExcludedType returns true for excluded types, such as unknown or ethernet within a container
func isExcludedType(ctx context.Context, t string) (bool, error) {
	if _, ok := excludedInterfaceTypes[t]; ok {
		return true, nil
	}
	runningContainer, err := RunningInContainer(ctx)
	if err != nil {
		return false, err
	}
	if runningContainer && t == "ethernet" {
		return true, nil
	}
	if strings.HasPrefix("unknown-", t) {
		return true, nil
	}
	return false, nil
}

// GetIPAddr executes machine-resources to fetch IP address and interface info
func GetIPAddr(ctx context.Context) (map[string]lxdresources.NetworkState, error) {
	cmdPath, err := GetResourcesBinPath()
	if err != nil {
		return nil, err
	}
	var args []string
	if IsRunningInSnap() {
		args = append(args, cmdPath)
		cmdPath = "/usr/bin/sudo"
	}
	cmd := exec.CommandContext(ctx, cmdPath, args...)
	out, err := cmd.Output()
	if err != nil {
		return nil, err
	}
	var info MachineInfo
	err = json.Unmarshal(out, &info)
	if err != nil {
		return nil, err
	}
	return info.Networks, nil
}

func splitDhclientCmdlineFile(data []byte, atEOF bool) (advance int, token []byte, err error) {
	for i := 0; i < len(data); i++ {
		if data[i] == '\x00' {
			return i + 1, data[:i], nil
		}
		if !atEOF {
			return 0, nil, nil
		}
	}
	return 0, data, bufio.ErrFinalToken
}

// GetLatestFixedAddress parses dhclient's leasefile for the latest fixed address
func GetLatestFixedAddress(leasePath string) (string, error) {
	if len(leasePath) == 0 {
		return "", nil
	}
	f, err := os.Open(leasePath)
	if err != nil {
		return "", err
	}
	defer f.Close()
	return getLatestFixedAddress(f)
}

func getLatestFixedAddress(leaseFile io.Reader) (string, error) {
	leaseBytes, err := io.ReadAll(leaseFile)
	if err != nil {
		return "", err
	}
	submatches := leaseRx.FindAllSubmatch(leaseBytes, -1)
	if len(submatches) > 0 {
		matches := submatches[len(submatches)-1]
		if len(matches) > 0 {
			lastLease := matches[len(matches)-1]
			for _, line := range strings.Split(string(lastLease), "\n") {
				line = strings.TrimSpace(line)
				if len(line) > 0 {
					lineList := strings.SplitN(line, " ", 2)
					if len(lineList) < 2 {
						continue
					}
					statement, value := lineList[0], lineList[1]
					if statement == "fixed-address" || statement == "fixed-address6" {
						return strings.TrimSpace(strings.SplitN(value, ";", 2)[0]), nil
					}
				}
			}
		}
	}
	return "", nil
}

// GetDhclientInfo reads dhclient's cmdline args for the path to the lease file and parses said lease file
func GetDhclientInfo(ctx context.Context, procPath string) (map[string]string, error) {
	if len(procPath) == 0 {
		procPath = "/proc"
	}
	pids, err := GetRunningPIDsWithCMD(ctx, "dhclient", "", false)
	if err != nil {
		return nil, err
	}
	info := make(map[string]string)
	for _, pid := range pids {
		cmdlinePath := filepath.Join(procPath, strconv.Itoa(pid), "cmdline")
		err = func() error {
			f, err := os.Open(cmdlinePath)
			if err != nil {
				return err
			}
			defer f.Close()
			scanner := bufio.NewScanner(f)
			scanner.Split(splitDhclientCmdlineFile)
			var (
				cmd       []string
				leasePath string
			)
			lfIdx := -1
			for scanner.Scan() {
				cmd = append(cmd, scanner.Text())
				if cmd[len(cmd)-1] == "-lf" {
					lfIdx = len(cmd) - 1
				}
				if lfIdx > -1 && len(cmd)-2 == lfIdx {
					leasePath = cmd[len(cmd)-1]
				}
			}
			ifaceName := cmd[len(cmd)-1]
			ipAddr, err := GetLatestFixedAddress(leasePath)
			if err != nil {
				return err
			}
			if len(ipAddr) > 0 && ipAddr != " " {
				info[ifaceName] = ipAddr
			}
			return nil
		}()
		if err != nil {
			return nil, err
		}
	}
	return info, nil
}

type IPLink struct {
	Netmask int
	Mode    string
	Address string
	Gateway string
}

type Vlan struct {
	LowerDev string
	Vid      uint64
}

type Interface struct {
	Type      string
	Mac       string
	Links     []IPLink
	Enabled   bool
	Vlan      *Vlan
	Source    string
	Parents   []string
	Monitored bool
}

type sortableSubnets []*net.IPNet

func (s sortableSubnets) Len() int {
	return len(s)
}

func (s sortableSubnets) Less(i, j int) bool {
	iPrefixlen, _ := s[i].Mask.Size()
	jPrefixlen, _ := s[j].Mask.Size()
	return iPrefixlen < jPrefixlen
}

func (s sortableSubnets) Swap(i, j int) {
	tmp := s[j]
	s[j] = s[i]
	s[i] = tmp
}

// fixLinkAddress fixes link addresses such that it finds a corresponding subnet for each
func fixLinkAddresses(links []IPLink) ([]IPLink, error) {
	var (
		subnetsV4 []*net.IPNet
		linksV4   []struct {
			Link IPLink
			Idx  int
		}
		subnetsV6 []*net.IPNet
		linksV6   []struct {
			Link IPLink
			Idx  int
		}
	)
	for i, link := range links {
		var (
			ipAddr net.IP
			ipNet  *net.IPNet
			err    error
		)
		if link.Netmask != 0 {
			ipAddr, ipNet, err = net.ParseCIDR(fmt.Sprintf("%s/%d", link.Address, link.Netmask))
		} else if !strings.Contains(link.Address, "/") {
			ipAddr, ipNet, err = net.ParseCIDR(fmt.Sprintf("%s/32", link.Address))
		} else {
			ipAddr, ipNet, err = net.ParseCIDR(link.Address)
		}
		if err != nil {
			return nil, err
		}
		prefixLen, _ := ipNet.Mask.Size()
		if ipAddr.To4() != nil {
			if prefixLen == 32 {
				linksV4 = append(linksV4, struct {
					Link IPLink
					Idx  int
				}{
					Link: link,
					Idx:  i,
				})
			} else {
				subnetsV4 = append(subnetsV4, ipNet)
			}
		} else {
			if prefixLen == 128 {
				linksV6 = append(linksV6, struct {
					Link IPLink
					Idx  int
				}{
					Link: link,
					Idx:  i,
				})
			} else {
				subnetsV6 = append(subnetsV6, ipNet)
			}
		}
	}
	newLinks := [][]struct {
		Link IPLink
		Idx  int
	}{linksV4, linksV6}
	newSubnets := [][]*net.IPNet{subnetsV4, subnetsV6}
	for i, currLinks := range newLinks {
		currSubnets := sortableSubnets(newSubnets[i])
		sort.Sort(sort.Reverse(currSubnets))
		for _, link := range currLinks {
			var (
				ip  net.IP
				err error
			)
			if link.Link.Netmask != 0 {
				ip, _, err = net.ParseCIDR(
					fmt.Sprintf("%s:%d", link.Link.Address, link.Link.Netmask),
				)
			} else if !strings.Contains(link.Link.Address, "/") {
				ip = net.ParseIP(link.Link.Address)
			} else {
				ip, _, err = net.ParseCIDR(link.Link.Address)
			}
			if err != nil {
				return nil, err
			}
			for _, subnet := range currSubnets {
				if subnet.Contains(ip) {
					prefixlen, _ := subnet.Mask.Size()
					if link.Link.Netmask != 0 {
						link.Link.Netmask = prefixlen
					} else {
						link.Link.Address = fmt.Sprintf("%s/%d", ip, prefixlen)
					}
				}
			}
			links[link.Idx] = link.Link
		}
	}
	return links, nil
}

type IPRoute struct {
	Gateway   string `json:"gateway"`
	GatewayIP net.IP `json:"-"`
	Dev       string `json:"dev"`
	Protocol  string `json:"protocol"`
	Metric    int    `json:"metric"`
	Flags     []int  `json:"flags"`
}

// GetIPRoute uses the ip command to fetch route info
func GetIPRoute(ctx context.Context) (map[string]IPRoute, error) {
	cmd := exec.CommandContext(ctx, "ip", "-json", "route", "list", "scope", "global")
	routes := make(map[string]IPRoute)
	var routeList []struct {
		Name string `json:"dst"`
		IPRoute
	}
	out, err := cmd.Output()
	if err != nil {
		return nil, err
	}
	err = json.Unmarshal(out, &routeList)
	if err != nil {
		return nil, err
	}
	for _, route := range routeList {
		route.IPRoute.GatewayIP = net.ParseIP(route.Gateway)
		routes[route.Name] = route.IPRoute
	}
	return routes, nil
}

// fixGateways attempts to find a corresponding gateway IP if one exists for each link
func fixGateways(links []IPLink, ipRouteInfo map[string]IPRoute) (res []IPLink, err error) {
	for i, link := range links {
		var subnet *net.IPNet
		if link.Netmask != 0 {
			_, subnet, err = net.ParseCIDR(fmt.Sprintf("%s/%d", link.Address, link.Netmask))
		} else {
			_, subnet, err = net.ParseCIDR(link.Address)
		}
		if err != nil {
			return nil, err
		}
		if routeInfo, ok := ipRouteInfo[subnet.String()]; ok {
			link.Gateway = routeInfo.Gateway
		} else if defaultInfo, ok := ipRouteInfo["default"]; ok && subnet.Contains(defaultInfo.GatewayIP) {
			link.Gateway = defaultInfo.Gateway
		}
		links[i] = link
	}
	return links, nil
}

// GetInterfaceChildren constructs a tree of interface names for each parent interface to child interfaces
func GetInterfaceChildren(interfaces map[string]Interface) map[string][]string {
	children := make(map[string][]string)
	for name, iface := range interfaces {
		for _, parent := range iface.Parents {
			if node, ok := children[parent]; ok {
				node = append(node, name)
			} else {
				children[parent] = []string{name}
			}
		}
	}
	return children
}

type InterfaceChild struct {
	Name  string
	Iface Interface
}

// InterfaceChildren gets the interface definitions for children of a given interface
func InterfaceChildren(ifname string, interfaces map[string]Interface, children map[string][]string) (res []InterfaceChild) {
	if node, ok := children[ifname]; ok {
		for _, child := range node {
			res = append(res, InterfaceChild{Name: child, Iface: interfaces[child]})
		}
	}
	return res
}

// GetDefaultMonitoredInterfaces sets which interfaces are monitored
func GetDefaultMonitoredInterfaces(interfaces map[string]Interface) (res map[string]struct{}) {
	res = make(map[string]struct{})
	childrenMap := GetInterfaceChildren(interfaces)
	for name, iface := range interfaces {
		if !iface.Enabled {
			continue
		}
		switch iface.Type {
		case "physical":
			shouldMonitor := true
			for _, child := range InterfaceChildren(name, interfaces, childrenMap) {
				if child.Iface.Type == "bond" {
					shouldMonitor = false
					break
				}
			}
			if shouldMonitor {
				res[name] = struct{}{}
			}
		case "bond":
			res[name] = struct{}{}
		case "bridge":
			if len(iface.Parents) == 0 {
				res[name] = struct{}{}
			}
		}
	}
	return res
}

// GetAllInterfacesDefinition fetchs all interface info for the local machine
func GetAllInterfacesDefinition(ctx context.Context, annotateWithMonitored bool) (map[string]Interface, error) {
	dhclientInfo, err := GetDhclientInfo(ctx, "")
	if err != nil {
		return nil, err
	}
	netIfaces, err := GetIPAddr(ctx)
	if err != nil {
		return nil, err
	}
	iprouteInfo, err := GetIPRoute(ctx)
	if err != nil {
		return nil, err
	}
	res := make(map[string]Interface)
	for name, iface := range netIfaces {
		excludeType, err := isExcludedType(ctx, iface.Type)
		if err != nil {
			return nil, err
		}
		if excludeType {
			continue
		}
		i := Interface{
			Mac:     iface.Hwaddr,
			Enabled: iface.State == "up",
		}
		if !(iface.Type == "vlan" || iface.Type == "bridge" || iface.Type == "bond") {
			i.Type = "physical"
		} else {
			i.Type = iface.Type
			if iface.Bond != nil && len(iface.Bond.LowerDevices) > 0 {
				i.Parents = append(i.Parents, iface.Bond.LowerDevices...)
			}
			if iface.Bridge != nil && len(iface.Bridge.UpperDevices) > 0 {
				i.Parents = append(i.Parents, iface.Bridge.UpperDevices...)
			}
		}
		if iface.VLAN != nil {
			i.Vlan = &Vlan{
				LowerDev: iface.VLAN.LowerDevice,
				Vid:      iface.VLAN.VID,
			}
			i.Parents = append(i.Parents, iface.VLAN.LowerDevice)
		}
		dhcpAddr := dhclientInfo[name]
		for _, addr := range iface.Addresses {
			mode := "static"
			if net.ParseIP(addr.Address).String() == dhcpAddr {
				mode = "dhcp"
			}

			link := IPLink{Mode: mode, Address: addr.Address}
			if len(addr.Netmask) > 0 {
				link.Netmask, err = strconv.Atoi(addr.Netmask)
				if err != nil {
					return nil, err
				}
			}
			i.Links = append(i.Links, link)
		}
		i.Links, err = fixLinkAddresses(i.Links)
		if err != nil {
			return nil, err
		}
		i.Links, err = fixGateways(i.Links, iprouteInfo)
		if err != nil {
			return nil, err
		}
		res[name] = i
	}
	if annotateWithMonitored {
		monitoredIfaces := GetDefaultMonitoredInterfaces(res)
		for name, iface := range res {
			if _, ok := monitoredIfaces[name]; ok {
				iface.Monitored = true
			} else {
				iface.Monitored = false
			}
			res[name] = iface
		}
	}
	return res, nil
}
