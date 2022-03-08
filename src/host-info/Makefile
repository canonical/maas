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
GO_CACHE_DIR := $(shell [ -d $(HOME)/.cache ] && echo $(HOME)/.cache/go-cache || mktemp --tmpdir -d tmp.go-cacheXXX)

.DEFAULT_GOAL := build

# XXX: Explicitly set GOCACHE to avoid situations where we can't mkdir $HOME/.cache (autopkgtest VM)
$(MACHINE_RESOURCES_BINARIES): vendor
	GOCACHE=$(GO_CACHE_DIR) GOARCH=$(DEB_GO_ARCH_$(notdir $@)) go build -mod vendor -ldflags '-s -w' -o $@ $(PACKAGE_DIR)

$(HARDWARE_SYNC_BINARIES): vendor
	GOCACHE=$(GO_CACHE_DIR) GOARCH=$(DEB_GO_ARCH_$(notdir $@)) go build -mod vendor -ldflags '-s -w' -o $@ $(HARDWARE_SYNC_DIR)

build: $(MACHINE_RESOURCES_BINARIES)
.PHONY: build

clean:
	rm -rf $(BINDIR) $(VENDOR_DIR)
.PHONY: clean

format:
	@go fmt $(PACKAGE_DIR)
.PHONY: format

install: $(MACHINE_RESOURCES_BINARIES)
	install -t $(DESTDIR)/usr/share/maas/machine-resources -D $(MACHINE_RESOURCES_BINARIES)
.PHONY: install

vendor:
	go mod vendor

update-deps:
	go get -u all
	go mod tidy
.PHONY: update-deps
