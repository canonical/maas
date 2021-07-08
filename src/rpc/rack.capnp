@0xed74792c33f7cbcf;

using Go = import "go.capnp";
using Controller = import "controller.capnp";

$Go.package("rpc");
$Go.import("rpc");

struct Placeholder {
    msg @0 :Text;
}

interface RackController extends(Controller.Controller) {
    todo @0 ();
}
