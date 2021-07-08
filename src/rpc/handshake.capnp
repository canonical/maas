@0xdceab81b996ed67b;

using Go = import "go.capnp";
$Go.package("rpc");
$Go.import("rpc");

using Network = import "network.capnp";

struct AuthResponse {
    salt @0 :Data;
    digest @1 :Data;
}

struct RegisterRequest {
    systemId @0 :Text;
    hostname @1 :Text;
    interfaces @2 :Network.Interfaces;
    url @3 :Text;
    nodegroup @4 :Text;
    beaconSupport @5 :Bool;
    version @6 :Text;
}

struct RegisterResponse {
    systemId @0 :Text;
    uuid @1 :Text;
    version @2 :Text;
}
