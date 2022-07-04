#
# Build the machine-resources binary on all supported platforms.
#

DEB_ARCHES := amd64 i386 armhf arm64 ppc64el s390x
# map deb to go architectures
DEB_GO_ARCH_amd64 = amd64
DEB_GO_ARCH_i386 = 386
DEB_GO_ARCH_armhf = arm
DEB_GO_ARCH_arm64 = arm64
DEB_GO_ARCH_ppc64el = ppc64le
DEB_GO_ARCH_s390x = s390x

BINDIR := bin
MACHINE_RESOURCES_BINARIES := $(addprefix $(BINDIR)/machine-resources/,$(DEB_ARCHES))
HARDWARE_SYNC_BINARIES := $(addprefix $(BINDIR)/hardware-sync/,$(DEB_ARCHES))

CMD_DIR := ./cmd
PACKAGE_DIR := $(CMD_DIR)/machine-resources
HARDWARE_SYNC_DIR := $(CMD_DIR)/hardware-sync
VENDOR_DIR := $(PACKAGE_DIR)/vendor
# Explicitly set cache dirs to avoid situations where we can't mkdir under $HOME (e.g. Launchpad builds)
export GOCACHE := $(shell [ -d $(HOME)/.cache ] && echo $(HOME)/.cache/go-cache || mktemp --tmpdir -d tmp.go-cacheXXX)
export GOMODCACHE := $(shell [ -d $(HOME)/go ] && echo $(HOME)/go/pkg/mod || mktemp --tmpdir -d tmp.go-mod-cacheXXX)

# build static binaries since they need to run on different Ubuntu releases
GO_BUILD := CGO_ENABLED=0 go build -mod=vendor -ldflags '-s -w -extldflags "-static"'

.DEFAULT_GOAL := build

$(MACHINE_RESOURCES_BINARIES): TARGET_DIR=$(PACKAGE_DIR)
$(HARDWARE_SYNC_BINARIES): TARGET_DIR=$(HARDWARE_SYNC_DIR)
$(HARDWARE_SYNC_BINARIES) $(MACHINE_RESOURCES_BINARIES):
	GOARCH=$(DEB_GO_ARCH_$(notdir $@)) $(GO_BUILD) -o $@ $(TARGET_DIR)

build: vendor/modules.txt $(MACHINE_RESOURCES_BINARIES) $(HARDWARE_SYNC_BINARIES)
.PHONY: build

# don't vendor dependencies before building binaries
build-no-vendor: $(MACHINE_RESOURCES_BINARIES) $(HARDWARE_SYNC_BINARIES)
.PHONY: build-no-vendor

clean:
	rm -rf $(BINDIR) $(VENDOR_DIR)
.PHONY: clean

format:
	@go fmt $(PACKAGE_DIR)
.PHONY: format

install: $(MACHINE_RESOURCES_BINARIES)
	install -t $(DESTDIR)/usr/share/maas/machine-resources -D $(MACHINE_RESOURCES_BINARIES)
.PHONY: install

vendor: vendor/modules.txt
.PHONY: vendor

vendor/modules.txt: go.mod
	go mod vendor

update-deps:
	go get -u all
	go mod tidy
.PHONY: update-deps
