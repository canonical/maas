@0xdae346a935a6f239;

using Go = import "go.capnp";
$Go.package("rpc");
$Go.import("rpc");

struct Link {
    mode @0 :Text;
    address @1 :Text;
    gateway @2 :Text;
    netmask @3 :Int32;
}

struct InterfaceDetails {
    macAddress @0 :Text;
    type @1 :Text;
    links @2 :List(Link);
    vid @3 :UInt64;
    enabled @4 :Bool;
    parents @5 :List(Text);
}

struct Interface {
    name @0 :Text;
    iface @1 :InterfaceDetails;
}

struct Interfaces {
    ifaces @0 :List(Interface);
}
