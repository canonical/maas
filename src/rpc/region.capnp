@0xa6582630060cca5f;

using Go = import "go.capnp";
using Controller = import "controller.capnp";
using Handshake = import "handshake.capnp";
using Network = import "network.capnp";
using Rack = import "rack.capnp";

$Go.package("rpc");
$Go.import("rpc");

struct ReportBootImagesRequest {
    uuid @0 :Text;
    images @1 :List(Controller.Image);
}

struct BootConfigRequest {
    systemId @0 :Text;
    localIP @1 :Text;
    remoteIP @2 :Text;
    arch @3 :Text;
    subarch @4 :Text;
    mac @5 :Text;
    hardwareUUID @6 :Text;
    biosBootMethod @7 :Text;
}

struct BootConfig {
    arch @0 :Text;
    subarch @1 :Text;
    osystem @2 :Text;
    release @3 :Text;
    kernel @4 :Text;
    initrd @5 :Text;
    bootDTB @6 :Text;
    purpose @7 :Text;
    hostname @8 :Text;
    domain @9 :Text;
    preseedURL @10 :Text;
    fsHost @11 :Text;
    logHost @12 :Text;
    logPort @13 :Int16;
    extraOpts @14 :Text;
    systemId @15 :Text;
    httpBoot @16 :Bool;
}

struct BootsourceSelection {
    os @0 :Text;
    release @1 :Text;
    arches @2 :List(Text);
}

struct Bootsource {
    url @0 :Text;
    keyringData @1 :Data;
    selections @2 :List(BootsourceSelection);
}

struct Bootsources {
    sources @0 :List(Bootsource);
}

struct ArchiveMirror {
    main @0 :Text;
    ports @1 :Text;
}

struct Proxies {
    http @0 :Text;
    https @1 :Text;
}

struct NodeFailedRequest {
    systemId @0 :Text;
    errorDescription @1 :Text;
}

struct NodePowerParameter {
    systemId @0 :Text;
    hostname @1 :Text;
    powerState @2 :Text;
    powerType @3 :Text;
    context @4 :Text;
}

struct NodePowerParameters {
    nodes @0 :List(NodePowerParameter);
}

struct PowerState {
    systemId @0 :Text;
    powerState @1 :Text;
}

struct EventType {
    name @0 :Text;
    description @1 :Text;
    level @2 :Int32;
}

struct Event {
    systemId @0 :Text;
    typeName @1 :Text;
    description @2 :Text;
}

struct EventMacAddress {
    macAddress @0 :Text;
    typeName @1 :Text;
    description @2 :Text;
}

struct EventIPAddress {
    ipAddress @0 :Text;
    typeName @1 :Text;
    description @2 :Text;
}

struct ForeignDHCPServer {
    systemId @0 :Text;
    interfaceName @1 :Text;
    dhcpIP @2 :Text;
}

struct MDNSReport {
    systemId @0 :Text;
    mDNS @1 :Controller.MDNS;
}

struct Neighbours {
    placeholder @0 :Text;
}

struct NeighbourReport {
    systemId @0 :Text;
    neighbours @1 :Neighbours;
}

struct CreateNodeRequest {
    architecture @0 :Text;
    powerType @1 :Text;
    powerParameters @2 :Text;
    macAddresses @3 :List(Text);
    hostname @4 :Text;
    domain @5 :Text;
}

struct CommissionNodeRequest {
    systemId @0 :Text;
    user @1 :Text;
}

struct PowerStateRequest {
    placeholder @0 :Text;
}

struct UpdateLeaseRequest {
    clusterUUID @0 :Text;
    action @1 :Text;
    mac @2 :Text;
    ipFamily @3 :Text;
    ip @4 :Text;
    timestamp @5 :Int64;
    leaseTime @6 :Int64;
    hostname @7 :Text;
}

struct UpdateServiceRequest {
    systemId @0 :Text;
    services @1 :List(Controller.Service);
}

struct ControllerState {
    placeholder @0 :Text;
}

struct UpdateControllerStateRequest {
    systemId @0 :Text;
    scope @1 :Text;
    state @2 :ControllerState;
}

interface RegionController extends(Controller.Controller) {
    interface Authenticator {
        authenticate @0 (msg :Data) -> (resp: Handshake.AuthResponse);
    }
    interface Registerer {
        register @0 (req :Handshake.RegisterRequest) -> (resp :Handshake.RegisterResponse);
    }
    interface RackController extends (Controller.Controller) {
        todo @0 ();
    }
    reportBootImages @0 (msg :ReportBootImagesRequest);
    getBootConfig @1 (msg :BootConfigRequest) -> (resp :BootConfig);
    getBootSources @2 (uuid :Text) -> (resp :Bootsources);
    getArchiveMirrors @3 () -> (resp :ArchiveMirror);
    getProxies @4 () -> (resp :Proxies);
    markNodeFailed @5 (msg :NodeFailedRequest);
    listNodePowerParameters @6 (uuid :Text) -> (resp :NodePowerParameters);
    updateLastImageSync @7 (systemId :Text);
    updateNodePowerState @8 (msg :PowerStateRequest);
    registerEventType @9 (msg :EventType);
    sendEvent @10 (msg :Event);
    sendEventMacAddress @11 (msg :EventMacAddress);
    sendEventIPAddress @12 (msg :EventIPAddress);
    reportForeignDHCPServer @13 (msg :ForeignDHCPServer);
    reportMDNSEntries @14 (msg :MDNSReport);
    reporrtNeighbours @15 (msg :NeighbourReport);
    createNode @16 (msg :CreateNodeRequest) -> (systemId :Text);
    commissionNode @17 (msg :CommissionNodeRequest);
    getDiscoveryState @18 (systemId :Text) -> (resp :List(Network.Interface));
    requestNodeInfoByMACAddress @19 (macAddress :Text) -> (node :Controller.Node);
    updateLease @20 (msg :UpdateLeaseRequest);
    updateService @21 (msg :UpdateServiceRequest);
    requestRackRefresh @22 (systemId :Text) -> (resp :Controller.RackSecret);
    getControllerType @23 (systemId :Text) -> (resp :Controller.ControllerTypeResponse);
    getTimeConfiguration @24 (systemId :Text) -> (resp :Controller.TimeConfiguration);
    getDNSConfiguration @25 (systemId :Text) -> (trustedNetworks :List(Text));
    getProxyConfiguration @26 (systemId :Text) -> (proxyConfig :Controller.ProxyConfiguration);
    getSyslogConfiguration @27 (systemId :Text) -> (port :Int16);
    updateControllerState @28 (msg :UpdateControllerStateRequest);
    getAuthenticator @29 () -> (auth :Authenticator);
    getRegisterer @30 (rackController :RackController) -> (reg :Registerer);
}
