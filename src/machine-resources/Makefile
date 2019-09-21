#
# Makefile to build the machine-resources binary on all relevant platforms.
#

ARCHES := amd64 386 arm arm64 ppc64le s390x
BINARIES = $(ARCHES)

.DEFAULT_GOAL := build

deps:
	go get -u github.com/lxc/lxd/lxd/resources
	go get -u github.com/tools/godep
.PHONY: deps

vendor:
	godep save
.PHONY: vendor

build: $(BINARIES)
.PHONY: build

$(ARCHES): deps
	GOARCH=$@ go build -ldflags '-s -w' -o $@ machine-resources.go
.PHONY: $(ARCHES)

clean:
	rm -f $(BINARIES)
	rm -rf vendor/ Godeps/
.PHONY: clean
