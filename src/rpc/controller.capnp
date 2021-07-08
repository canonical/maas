@0xb67314e4a0c9d120;

using Go = import "go.capnp";

$Go.package("rpc");
$Go.import("rpc");

struct MDNS {
    todo @0 :Text;
}

struct Node {
    systemId @0 :Text;
    hostname @1 :Text;
    status @2 :Int32;
    bootType @3 :Text;
    osystem @4 :Text;
    distroSeries @5 :Text;
    architexture @6 :Text;
    purpose @7 :Text;
}

struct Image {
    architecture @0 :Text;
    subarchitecture @1 :Text;
    release @2 :Text;
    purpose @3 :Text;
}

struct Service {
    name @0 :Text;
    status @1 :Text;
    statusInfo @2 :Text;
}

struct RackSecret {
    consumerKey @0 :Text;
    tokenKey @1 :Text;
    tokenSecret @2 :Text;
}

struct ControllerTypeResponse {
    isRegion @0 :Bool;
    isRack @1 :Bool;
}

struct TimeConfiguration {
    servers @0 :List(Text);
    peers @1 :List(Text);
}

struct ProxyConfiguration {
    enabled @0 :Bool;
    port @1 :Int16;
    allowedCidrs @2 :List(Text);
    preferV4Proxy @3 :Bool;
}

interface Controller {
    ping @0 ();
}
