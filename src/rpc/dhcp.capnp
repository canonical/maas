@0xccd3d5a002a5cb57;

using Go = import "go.capnp";

$Go.package("rpc");
$Go.import("rpc");

struct FailoverPeer {
    name @0 :Text;
    mode @1 :Text;
    address @2 :Text;
    peerAddress @3 :Text;
}

struct DHCPSnippet {
    name @0 :Text;
    description @1 :Text;
    value @2 :Text;
}

struct Pool {
    ipRangeLow @0 :Text;
    ipRangeHigh @1 :Text;
    failoverPeer @2 :Text;
    dhcpSnippets @3 :List(DHCPSnippet);
}

struct Subnet {
    subnet @0 :Text;
    subnetMask @1 :Text;
    subnetCIDR @2 :Text;
    broadcastIP @3 :Text;
    routerIP @4 :Text;
    dnsServers @5 :List(Text);
    ntpServers @6 :List(Text);
    domainName @7 :Text;
    searchList @8 :List(Text);
    pools @9 :List(Pool);
    dhcpSnippets @10 :List(DHCPSnippet);
    disabledBootArchitectures @11 :List(Text);
}

struct SharedNetwork {
    name @0 :Text;
    subnets @1 :List(Subnet);
    mtu @2 :Int32;
    iface @3 :Text;
}

struct Host {
    host @0 :Text;
    mac @1 :Text;
    ip @2 :Text;
    dhcpSnippets @3 :List(DHCPSnippet);
}

struct ConfigureDHCPReq {
    omapiKey @0 :Text;
    failoverPeers @1 :List(FailoverPeer);
    sharedNetworks @2 :List(SharedNetwork);
    hosts @3 :List(Host);
    interfaces @4 :List(Text);
    globalDHCPSnippets @5 :List(DHCPSnippet);
}

