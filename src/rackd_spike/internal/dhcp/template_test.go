package dhcp

import (
	"bytes"
	"strings"
	"testing"

	machinehelpers "rackd/internal/machine_helpers"

	"github.com/stretchr/testify/assert"
)

func TestRenderDhcpdConf(t *testing.T) {
	table := []struct {
		Name string
		In   TemplateData
		Out  string
		Err  error
	}{
		{
			Name: "basic-template",
			In: TemplateData{
				GlobalDHCPSnippets: []DhcpSnippet{
					{
						Name:        "global-snippet-test",
						Description: "test",
						Value:       "",
					},
				},
				FailoverPeers: []FailoverPeer{
					{
						Name:        "test-failover-peer-primary",
						Mode:        "primary",
						Address:     "10.0.0.2",
						PeerAddress: "10.0.0.3",
					}, {
						Name:        "test-failover-peer-secondary",
						Mode:        "secondary",
						Address:     "10.0.0.3",
						PeerAddress: "10.0.0.2",
					},
				},
				SharedNetworks: []SharedNetwork{
					{
						Name: "test-shared-network",
						Subnets: []Subnet{
							{
								Subnet:         "10.0.0.0/24",
								SubnetMask:     "255.255.255.0",
								NextServer:     "10.0.0.2",
								BroadcastIP:    "10.0.0.255",
								DNSServers:     []string{"1.1.1.1"},
								DomainName:     "maas",
								SearchList:     []string{"maas"},
								RouterIP:       "10.0.0.1",
								NTPServersIPv4: "10.0.0.2",
								NTPServersIPv6: "fe80::e922:d79c:9818:f397",
								MTU:            1500,
								Pools: []Pool{
									{
										FailoverPeer: "test-failover-peer-primary",
										IPRangeLow:   "10.0.0.4",
										IPRangeHigh:  "10.0.0.28",
									},
								},
							},
						},
					},
				},
				Hosts: []Host{
					{
						Host: "test.maas",
						MAC:  "de:ad:c0:de:ca:fe",
						IP:   "10.0.0.29",
					},
				},
				DHCPHelper: DefaultDHCPHelper,
				DHCPSocket: machinehelpers.GetMAASDataPath(DefaultDHCPSocket),
				OMAPIKey:   "1234",
			},
			Out: `# WARNING: Do not edit /var/lib/maas/dhcpd.conf yourself.  MAAS will
# overwrite any changes made there.  Instead, you can modify dhcpd.conf by
# using DHCP snippets over the API or through the web interface.

option arch code 93 = unsigned integer 16; # RFC4578
option path-prefix code 210 = text; #RFC5071

#
# Shorter lease time for PXE booting
#
class "PXE" {
   match if substring (option vendor-class-identifier, 0, 3) = "PXE";
   default-lease-time 30;
   max-lease-time 30;
}

#
# Define lease time globally (can be overriden globally or per subnet
# with a DHCP snippet)
#
default-lease-time 600;
max-lease-time 600;

#
# Global DHCP snippets
#

# Name: global-snippet-test
# Description: test


#
# Failover Peers
#

failover peer test-failover-peer-primary {
    primary;
    address 10.0.0.2;
    peer address 10.0.0.3;
    max-response-delay 60;
    max-unacked-updates 10;
    load balance max seconds 3;

	mclt 3600;
    split 255;

}

failover peer test-failover-peer-secondary {
    secondary;
    address 10.0.0.3;
    peer address 10.0.0.2;
    max-response-delay 60;
    max-unacked-updates 10;
    load balance max seconds 3;

}


#
# Networks
#

shared-network test-shared-network {

    subnet 10.0.0.0/24 netmask 255.255.255.0 {
        ignore-client-uids true;
        next-server 10.0.0.2;
        option subnet-mask 255.255.255.0;
        option broadcast-address 10.0.0.255;
        option domain-name-servers 1.1.1.1;
        option domain-name "maas";
        option domain-search "maas";
        option routers 10.0.0.1;
        option ntp-servers 10.0.0.2;
        option dhcp6.sntp-servers fe80::e922:d79c:9818:f397;



		# No DHCP snippets defined for subnet



        pool {
            failover peer "test-failover-peer-primary";


			# No DHCP snippets for pool


            range 10.0.0.4 10.0.0.28;
        }

    }

}


#
# Hosts
#

# test.maas
host de-ad-c0-de-ca-fe {
    #
    # Node DHCP snippets
    #

	# No DHCP Snippets defined for host


	hardware ethernet de:ad:c0:de:ca:fe;
    fixed-address 10.0.0.29;
}


#
# Notify MAAS
#
on commit {
    set clhw = binary-to-ascii(16, 8, ":", substring(hardware, 1, 6));
    set clip = binary-to-ascii(10, 8, ".", leased-address);
    set cllt = binary-to-ascii(10, 32, "", encode-int(lease-time, 32));
    execute(
        "/usr/sbin/maas-dhcp-helper", "notify",
        "--action", "commit", "--mac", clhw,
        "--ip-family", "ipv4", "--ip", clip,
        "--lease-time", cllt, "--hostname", clht,
        "--socket", "/var/lib/maas/dhcpd.sock",
    );
}
on expiry {
    set clhw = binary-to-ascii(16, 8, ":", substring(hardware, 1, 6));
    set clip = binary-to-ascii(10, 8, ".", leased-address);
    execute(
        "/usr/sbin/maas-dhcp-helper", "notify",
        "--action", "expiry", "--mac", clhw,
        "--ip-family", "ipv4", "--ip", clip,
        "--socket", "/var/lib/maas/dhcpd.sock",
    );
}
on relase {
    set clhw = binary-to-ascii(16, 8, ":", substring(hardware, 1, 6));
    set clip = binary-to-ascii(10, 8, ".", leased-address);
    execute(
        "/usr/sbin/maas-dhcp-helper", "notify",
        "--action", "release", "--mac", clhw,
        "--ip-family", "ipv4", "--ip", clip,
        "--socket", "/var/lib/maas/dhcpd.sock",
    );
}

omapi-port 7911;
key omapi_key {
    algorithm HMAC-MD5;
    secret "1234";
};
omapi-key omapi_key;
`,
		},
	}
	for _, tcase := range table {
		t.Run(tcase.Name, func(tt *testing.T) {
			buf := &bytes.Buffer{}
			err := RenderDhcpdConf(buf, tcase.In)
			if err != nil {
				tt.Fatal(err)
			}
			out := buf.String()
			assert.Equal(
				tt,
				strings.ReplaceAll(strings.ReplaceAll(strings.TrimSpace(tcase.Out), "\t", ""), " ", ""),
				strings.ReplaceAll(strings.ReplaceAll(strings.TrimSpace(out), "\t", ""), " ", ""),
			)
		})
	}
}

func TestRenderDhcpd6Conf(t *testing.T) {
	table := []struct {
		Name string
		In   TemplateData
		Out  string
		Err  error
	}{
		{
			Name: "basic-dhcpd6.conf",
			In: TemplateData{
				GlobalDHCPSnippets: []DhcpSnippet{
					{
						Name:        "test-global-dhcp-snippet",
						Description: "test",
					},
				},
				FailoverPeers: []FailoverPeer{
					{
						Name:        "test-primary",
						Mode:        "primary",
						Address:     "ffff:ffff::1",
						PeerAddress: "ffff:ffff::2",
					}, {
						Name:        "test-secondary",
						Mode:        "secondary",
						Address:     "ffff:ffff::2",
						PeerAddress: "ffff:ffff::1",
					},
				},
				SharedNetworks: []SharedNetwork{
					{
						Name: "test-shared-network",
						Subnets: []Subnet{
							{
								Subnet:         "ffff:ffff::/64",
								CIDR:           "ffff:ffff::/64",
								NextServer:     "ffff:ffff::1",
								DNSServers:     []string{"ffff:ffff::1"},
								DomainName:     "maas",
								SearchList:     []string{"maas"},
								RouterIP:       "ffff:ffff::1",
								NTPServersIPv4: "10.0.0.2",
								NTPServersIPv6: "ffff:ffff::1",
								MTU:            1500,
								Pools: []Pool{
									{
										FailoverPeer: "test-primary",
										IPRangeLow:   "ffff:ffff::4",
										IPRangeHigh:  "ffff:ffff::28",
									},
								},
							},
						},
					},
				},
				Hosts: []Host{
					{
						Host: "test-host.maas",
						MAC:  "de:ad:c0:de:ca:fe",
						IP:   "ffff:ffff::29",
					},
				},
				OMAPIKey: "1234",
			},
			Out: `# WARNING: Do not edit /var/lib/maas/dhcpd6.conf yourself.  MAAS will
# overwrite any changes made there.  Instead, you can modify dhcpd6.conf by
# using DHCP snippets over the API or through the web interface.

option dhcp6.user-class code 15 = string;
option dhcp6.client-arch-type code 61 = array of unsigned integer 16; # RFC5970
option dhcp6.vendor-class code 16 = {integer 32, integer 16, string};
option path-prefix code 210 = text; #RFC5071

#
# Define lease time globally (can be overriden globally or per subnet
# with a DHCP snippet)
#
default-lease-time 1800;
max-lease-time 1800;

#
# Global DHCP snippets
#

# Name: test-global-dhcp-snippet
# Description: test 



#
# Networks
#

shared-network test-shared-network {
    
    subnet6 ffff:ffff::/64 {
        # Bootloaders
        
        ignore-client-uids true;
        
        option dhcp6.name-servers ffff:ffff::1;
        
        option domain-name "maas";
        
        option dhcp6.domain-search "maas";
        

        # DHCPv6 does not have a router option (although there has been a
        # draft proposal for one).  Clients should get their routes from
        # route advertisements, or use custom options configured into both
        # the server and the client:
        # http://www.isc.org/blogs/routing-configuration-over-dhcpv6-2/
        #
        #option routers ffff:ffff::1;

        
        option ntp-servers 10.0.0.2;
        
        
        option dhcp6.sntp-servers ffff:ffff::1;
        

        #
        # Subnet DHCP snippets
        #
        
        # No DHCP snippets defined for subnet
        

        
        pool6 {
           
           # No DHCP snippets for pool
           

           range6 ffff:ffff::4 ffff:ffff::28;
        }
        
    }
    
}


#
# Hosts
#

# test-host.maas
host de-ad-c0-de-ca-fe {
   #
   # Node DHCP snippets
   #
   
   # No DHCP snippets defined for host
   

   hardware ethernet de:ad:c0:de:ca:fe;
   fixed-address6 ffff:ffff::29;
}


omapi-port 7912;
key omapi_key {
    algorithm HMAC-MD5;
    secret "1234";
};
omapi-key omapi_key;
`,
		},
	}
	for _, tcase := range table {
		t.Run(tcase.Name, func(tt *testing.T) {
			buf := &bytes.Buffer{}
			err := RenderDhcpd6Conf(buf, tcase.In)
			if err != nil {
				tt.Fatal(err)
			}
			out := buf.String()
			assert.Equal(
				tt,
				strings.ReplaceAll(tcase.Out, "\t", ""),
				strings.ReplaceAll(out, "\t", ""),
			)
		})
	}
}
