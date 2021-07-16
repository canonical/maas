package dhcp

import (
	"bytes"
	"fmt"
	"html/template"
	"io"
	"os"
	"path/filepath"
	"sort"

	"rackd/internal/boot"
	machinehelpers "rackd/internal/machine_helpers"
	"rackd/internal/templates"
)

const (
	DhcpdConfFileName  = "dhcpd.conf"
	Dhcpd6ConfFileName = "dhcpd6.conf"
	DefaultDHCPSocket  = "dhcpd.sock"
	DefaultDHCPHelper  = "/usr/sbin/maas-dhcp-helper"
	DefaultBootloader  = `
{{ if .IPv6 }}
else {
	# {{ .Name }}
	option dhcp6.bootfile-url "{{ .URL }}";
	{{ if .PathPrefixForce }}
	if exists dhcp6.oro {
		# Always send the PXELINUX option (path-prefix)
		option dhcp6.oro = concat(option dhcp6.oro,00d2);
	}
	{{ end }}
{{ else }}
else {
	# {{ .Name }}
	filename "{{ .Bootloader }}";
	{{ if .PathPrefix }}
	option path-prefix "{{ .PathPrefix }}";
	{{ end }}
	{{ if .PathPrefixForce }}
	if exists dhcp-parameter-request-list {
		# Always send the PXELINUX option (path-prefix)
		option dhcp-parameter-request-list = concat(
			iotuin dhcp-parameter-request-list,d2);
	}
	{{ end }}
{{ end }}
`
	ConditionalBootloader = `
{{ if .IPv6 }}
{{ if .UserClass }}
{{ .Behaviour }} exists dhcp6.user-class and
  option dhcp6.user-class = "{{ .UserClass }}" {
    # {{ .Name }}
	option dhcp6.bootfile-url "{{ .URL }}";
	{{ if .PathPrefixForce }}
	if exists dhcp6.oro {
		# Always send the PXELINUX option (path-prefix)
		option dhcp6.oro = concat(option dhcp6.oro,00d2);
	}
	{{ end }}
	{{ if .HTTPClient }}
	option dhcp6.vendor-class 0 10 "HTTPClient";
	{{ end }}
}
{{ else }}
{{ .Behaviour }} exists dhcp6.client-arch-type and
  option dhcp6.client-arch-type = {{ .ArchOctet }} {
    # {{ .Name }}
	option dhcp6.bootfile-url "{{ .URL }}";
	{{ if .PathPrefixForce }}
	if exists dhcp6.oro {
		# Always send the PXELINUX option (path-prefix)
		option dhcp6.oro = concat(option dhcp6.oro,00d2);
	}
	{{ end }}
	{{ if .HTTPClient }}
	option vendor-class-identifier "HTTPClient";
	{{ end }}
}
{{ end }}
{{ else }}
{{ if .UserClass }}
{{ .Behaviour }} option user-class = "{{ .UserClass }}" {
	# {{ .Name }}
	filename "{{ .Bootloader }}";
	{{ if .PathPrefix }}
	option path-prefix "{{ .PathPrefix }}";
	{{ end }}
	{{ if .PathPrefixForce }}
	if exists dhcp-parameter-request-list {
		# Always send the PXELINUX option (path-prefix)
		option dhcp-parameter-request-list = concat(
			option dhcp-parameter-request-list,d2);
	}
	{{ end }}
	{{ if .HTTPClient }}
	option vendor-class-identifier "HTTPClient";
	{{ end }}
}
{{ else }}
{{ .Behaviour }} option arch = {{ .ArchOctet }} {
	# {{ .Name }}
	filename "{{ .Bootloader }}";
	{{ if .PathPrefix }}
	option path-prefix "{{ .PathPrefix }}";
	{{ end }}
	{{ if .PathPrefixForce }}
	if exists dhcp-parameter-request-list {
		# Always send the PXELINUX option (path-prefix)
		option dhcp-parameter-request-list = concat(
			option dhcp-parameter-request-list,d2);
	}
	{{ end }}
	{{ if .HTTPClient }}
	option vendor-class-identifier "HTTPClient";
	{{ end }}
}
{{ end }}
{{ end }}
`
)

var (
	conditionalBootloaderTemplate = template.Must(
		template.New("conditional_bootloader").Parse(ConditionalBootloader),
	)
	defaultBootloaderTemplate = template.Must(
		template.New("default_bootloader").Parse(DefaultBootloader),
	)
)

type DhcpSnippet struct {
	templates.TemplateData
	Name        string
	Description string
	Value       string
}

type FailoverPeer struct {
	templates.TemplateData
	Name        string
	Mode        string
	Address     string
	PeerAddress string
}

type Pool struct {
	templates.TemplateData
	FailoverPeer string
	DHCPSnippets []DhcpSnippet
	IPRangeLow   string
	IPRangeHigh  string
}

type Subnet struct {
	templates.TemplateData
	Subnet         string
	SubnetMask     string
	CIDR           string
	NextServer     string
	BroadcastIP    string
	DNSServers     []string
	DomainName     string
	SearchList     []string
	RouterIP       string
	NTPServersIPv4 string
	NTPServersIPv6 string
	MTU            int
	Bootloader     string
	DHCPSnippets   []DhcpSnippet
	Pools          []Pool
}

type SharedNetwork struct {
	templates.TemplateData
	Name    string
	Subnets []Subnet
}

type Host struct {
	templates.TemplateData
	Host         string
	MAC          string
	DHCPSnippets []DhcpSnippet
	IP           string
}

type TemplateData struct {
	templates.TemplateData
	GlobalDHCPSnippets []DhcpSnippet
	FailoverPeers      []FailoverPeer
	SharedNetworks     []SharedNetwork
	Hosts              []Host
	DHCPHelper         string
	DHCPSocket         string
	OMAPIKey           string
}

type ConditionalBootloaderData struct {
	IPv6                      bool
	RackIP                    string
	DisabledBootArchitectures []string
}

type BootloaderData struct {
	IPv6            bool
	Behaviour       string
	ArchOctet       string
	Bootloader      string
	PathPrefix      string
	Name            string
	URL             string
	UserClass       string
	PathPrefixForce bool
}

func getConfPath(configFile string) string {
	if machinehelpers.IsRunningInSnap() {
		snapPaths := machinehelpers.SnapPaths{}
		return filepath.Join(snapPaths.FromEnv()["data"], machinehelpers.GetMAASDataPath(configFile))
	}
	return machinehelpers.GetMAASDataPath(configFile)
}

func GetDhcpdConfPath() string {
	return getConfPath(DhcpdConfFileName)
}

func GetDhcpd6ConfPath() string {
	return getConfPath(Dhcpd6ConfFileName)
}

func RenderDhcpdConfToFile(data TemplateData) error {
	f, err := os.OpenFile(GetDhcpdConfPath(), os.O_CREATE|os.O_RDWR, 0644)
	if err != nil {
		return err
	}
	defer func() {
		closeErr := f.Close()
		if err == nil { // don't overwrite err if something errored earlier
			err = closeErr
		}
	}()
	return RenderDhcpdConf(f, data)
}

func RenderDhcpd6ConfToFile(data TemplateData) error {
	f, err := os.OpenFile(GetDhcpd6ConfPath(), os.O_CREATE|os.O_RDWR, 0644)
	if err != nil {
		return err
	}
	defer func() {
		closeErr := f.Close()
		if err == nil { // don't overwrite err if something errored earlier
			err = closeErr
		}
	}()
	return RenderDhcpd6Conf(f, data)
}

func RenderDhcpdConf(dest io.Writer, data TemplateData) error {
	return templates.Render(dest, data, DhcpdConfFileName+".template")
}

func RenderDhcpd6Conf(dest io.Writer, data TemplateData) error {
	return templates.Render(dest, data, Dhcpd6ConfFileName+".template")
}

func fmtBootURL(data ConditionalBootloaderData, method boot.BootMethod) string {
	useHTTP := len(method.ArchOctet) > 0 || method.HTTPURL
	schema := "tftp"
	var (
		port string
		url  string
	)
	if useHTTP {
		schema = "http"
		port = ":5248"
	}
	if data.IPv6 {
		url = fmt.Sprintf("%s://[%s]%s/", schema, data.RackIP, port)
	} else {
		url = fmt.Sprintf("%s://%s%s/", schema, data.RackIP, port)
	}
	if method.HTTPURL {
		url = fmt.Sprintf("%simages/", url)
	}
	url = string(append([]byte(url), method.BootloaderPath...))
	return url
}

func ComposeConditionalBootloader(data ConditionalBootloaderData) (string, error) {
	buf := &bytes.Buffer{}
	sort.Strings(data.DisabledBootArchitectures)
	first := true
	for name, method := range boot.BootMethodRegistry {
		if len(method.ArchOctet) == 0 && len(method.UserClass) == 0 {
			continue
		} else if sort.SearchStrings(data.DisabledBootArchitectures, name) >= 0 {
			continue
		}
		url := fmtBootURL(data, method)
		bootloader := method.BootloaderPath
		pathPrefix := method.PathPrefix
		if len(method.PathPrefix) > 0 {
			url = fmt.Sprintf("%s%s", url, method.PathPrefix)
		}
		if method.PathPrefixHTTP {
			pathPrefix = url
		}
		if method.AbsoluteURLAsFileName {
			bootloader = url
			pathPrefix = ""
		}
		tmplData := BootloaderData{
			IPv6:            data.IPv6,
			Name:            method.Name,
			UserClass:       method.UserClass,
			ArchOctet:       method.ArchOctet,
			URL:             url,
			PathPrefix:      pathPrefix,
			PathPrefixForce: method.PathPrefixForce,
			Bootloader:      bootloader,
		}
		if first {
			tmplData.Behaviour = "if"
			first = false
		} else {
			tmplData.Behaviour = "elsif"
		}
		err := conditionalBootloaderTemplate.Execute(buf, tmplData)
		if err != nil {
			return "", err
		}
	}
	method := boot.BootMethodRegistry["pxe"]
	if data.IPv6 {
		method = boot.BootMethodRegistry["uefi_amd64_tftp"]
	}
	if len(method.Name) == 0 {
		return buf.String(), nil
	}
	url := fmtBootURL(data, method)
	pathPrefix := method.PathPrefix
	if len(method.PathPrefix) > 0 {
		url = fmt.Sprintf("%s%s", url, method.PathPrefix)
	}
	if method.PathPrefixHTTP {
		pathPrefix = url
	}
	tmplData := BootloaderData{
		Name:            method.Name,
		UserClass:       method.UserClass,
		PathPrefixForce: method.PathPrefixForce,
		PathPrefix:      pathPrefix,
		ArchOctet:       method.ArchOctet,
	}
	err := defaultBootloaderTemplate.Execute(buf, tmplData)
	if err != nil {
		return "", err
	}
	return buf.String(), nil
}
