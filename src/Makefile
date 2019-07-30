#
# Makefile to build the machine-resources binary on all relevant platforms.
#

ARCHES := amd64 386 arm arm64 ppc64le s390x

BINARIES = $(addprefix $(BINARY_PREFIX), $(ARCHES))

.DEFAULT_GOAL := build

deps:
	go get -v github.com/lxc/lxd/lxd/resources
.PHONY: deps

build: deps $(BINARIES)
.PHONY: build

$(BINARY_PREFIX)%: %
	@true  # to force the rule to execute

$(ARCHES):
	GOARCH=$@ go build -o $@ machine-resources.go
.PHONY: $(ARCHES)

clean:
	rm -f $(BINARIES)
.PHONY: clean
