# Rackd

## Setup

### Dependencies

- Golang (>= 1.16)
- capnp
  - go: [repo](https://github.com/capnproto/go-capnproto2)
  - cli: [repo](https://github.com/sandstorm-io/capnproto.git)
  - python: [repo](https://github.com/capnproto/pycapnp)

#### capnp install

```
git clone https://github.com/sandstorm-io/capnproto.git
cd capnproto
autoreconf -i
./configure
make
sudo make install

go install capnproto.org/go/capnp/v3/capnpc-go

pip install Cython pycapnp
```

#### adding new capnp files

```
capnp id > myfile.capnp
# edit myfile.capnp
# add myfile.capnp as a make dependency to the gen-capnp-go in ./Makefile
# add myfile.capnp as a make dependency to the gen-capnp-setup in ../../Makefile
# edit ../rpc/py/setup_capnp.py to include myfile.capnp
make build # will generate the Go capnp code and build the rackd binary
cd ../../ && make gen-capnp-py # compiles the native extension and generates the python capnp code
```

## About the RPC communication

Rackd relies on Cap'n Proto's ability to do bidirectional RPC on a single TCP connection.  This is accomplished via Cap'n Proto's promise pipelining.
By having the client side initialize and bootstrap, it receives an interface for a region controller automatically. Prior to a call to `RegionController.Register()`, the RPC communication only flows from rack to region. Once the register call is made, passing a rack controller interface as an argument, the server side (the region controller),
now has an interface to make RPC calls to the rack controller as well.

## Directory Layout

```
├── cmd
|   # command entrypoint, subcommands, logger and other cmdline specific code
├── go.mod
├── go.sum
├── internal
│   ├── config # code for reading configuration
│   ├── machine_helpers # code for fetching local machine info
│   ├── metrics # code for exporting metrics via prometheus
│   ├── service # process supervisor code
│   └── transport # protocol specific code
├── Makefile
├── pkg
│   └── rpc # capnp generated code
|   └── # RPC handlers, both client and/or server implementations
└── README.rst
```

## Build

`make build`

## Running

```
cd ../../ # move to maas root dir, unless specified rackd will look for the machine-resources bin in $PWD/src/machine-resources/bin/<arch>
sudo ./src/rackd_spike/build/rackd # sudo is required for machine-resources
```
