PWD:=$(shell dirname $(realpath $(firstword $(MAKEFILE_LIST))))
ROOT_DIR:=$(shell dirname $(PWD))
RPC_DIR:=$(PWD)/pkg/rpc
VERSION:=develop-$(shell git rev-list -1 HEAD)

PATH:=$(shell go env GOPATH)/bin:${PATH}
export PATH

LDFLAGS="-X main.Version=$(VERSION) -s -w"

.PHONY: all
all: version test build

version:
	@go version

.PHONY: build
build: rackd

.PHONY: build-dir
build-dir:
	mkdir -p ./build

.PHONY: rackd
rackd: build-dir gen-capnp
	go build -ldflags $(LDFLAGS) -o ./build/rackd ./cmd/rackd.go

.PHONY: test
test:
	go test ./...

.PHONY: lint
lint:
	go vet ./...

.PHONY: format
format:
	gofmt -s -d ./cmd ./internal ./pkg

.PHONY: capnp-dir
capnp-dir:
	mkdir -p ./pkg/rpc

%.capnp: capnp-dir
	capnp compile -ogo:$(PWD)/pkg/rpc $(ROOT_DIR)/rpc/$@ --src-prefix $(ROOT_DIR)/rpc

.PHONY: gen-capnp
gen-capnp: handshake.capnp network.capnp region.capnp rack.capnp controller.capnp
