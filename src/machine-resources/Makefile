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
BINARIES := $(addprefix $(BINDIR)/,$(DEB_ARCHES))

PACKAGE_DIR := ./cmd/machine-resources
VENDOR_DIR := $(PACKAGE_DIR)/vendor
GO_CACHE_DIR := $(shell [ -d $(HOME)/.cache ] && echo $(HOME)/.cache/go-cache || mktemp --tmpdir -d tmp.go-cacheXXX)

.DEFAULT_GOAL := build

# XXX: Explicitly set GOCACHE to avoid situations where we can't mkdir $HOME/.cache (autopkgtest VM)
$(BINARIES): vendor
	GOCACHE=$(GO_CACHE_DIR) GOARCH=$(DEB_GO_ARCH_$(notdir $@)) go build -mod vendor -ldflags '-s -w' -o $@ $(PACKAGE_DIR)

build: $(BINARIES)
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

vendor:
	go mod vendor

update-deps:
	go get -u all
	go mod tidy
.PHONY: update-deps
