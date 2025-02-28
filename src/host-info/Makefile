#
# Build the machine-resources binary on all supported platforms.
#

DEB_ARCHES := amd64 i386 armhf arm64 ppc64el riscv64 s390x
# map deb to go architectures
DEB_GO_ARCH_amd64 = amd64
DEB_GO_ARCH_i386 = 386
DEB_GO_ARCH_armhf = arm
DEB_GO_ARCH_arm64 = arm64
DEB_GO_ARCH_ppc64el = ppc64le
DEB_GO_ARCH_riscv64 = riscv64
DEB_GO_ARCH_s390x = s390x

BINDIR := bin
BINARIES := $(addprefix $(BINDIR)/,$(DEB_ARCHES))

CMD_DIR := ./cmd
PACKAGE_DIR := $(CMD_DIR)/machine-resources
VENDOR_DIR := $(PACKAGE_DIR)/vendor
# Explicitly set cache dirs to avoid situations where we can't mkdir under $HOME (e.g. Launchpad builds)
export GOCACHE := $(shell [ -d $(HOME)/.cache ] && echo $(HOME)/.cache/go-cache || mktemp --tmpdir -d tmp.go-cacheXXX)
export GOMODCACHE := $(shell [ -d $(HOME)/go ] && echo $(HOME)/go/pkg/mod || mktemp --tmpdir -d tmp.go-mod-cacheXXX)

# build static binaries since they need to run on different Ubuntu releases
GO_BUILD := CGO_ENABLED=0 go build -mod=vendor -ldflags '-s -w -extldflags "-static"'

.DEFAULT_GOAL := build

$(BINARIES):
	GOARCH=$(DEB_GO_ARCH_$(notdir $@)) $(GO_BUILD) -o $@ $(PACKAGE_DIR)

build:
# call targets separately to work with parallel builds
	$(MAKE) vendor/modules.txt
	$(MAKE) $(BINARIES)
.PHONY: build

clean:
	rm -rf $(BINDIR) $(VENDOR_DIR)
.PHONY: clean

format:
	@go fmt $(PACKAGE_DIR)
.PHONY: format

install: $(BINARIES)
	install -t $(DESTDIR)/usr/share/maas/machine-resources -D $(BINARIES)
.PHONY: install

test: vendor
	CGO_ENABLED=1 go test -race ./...
.PHONY: test

test-cover: vendor
	CGO_ENABLED=1 go test -coverprofile=cover.out ./...
.PHONY: test-cover

vendor: vendor/modules.txt
.PHONY: vendor

vendor/modules.txt: go.mod
	go mod vendor

update-deps:
	go get -u all
	go mod tidy
.PHONY: update-deps
