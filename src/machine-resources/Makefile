#
# Makefile to build the machine-resources binary on all relevant platforms.
#

DEB_ARCHES := amd64 i386 armhf arm64 ppc64el s390x

GOARCH_amd64 = amd64
GOARCH_i386 = 386
GOARCH_armhf = arm
GOARCH_arm64 = arm64
GOARCH_ppc64el = ppc64le
GOARCH_s390x = s390x

export GOPATH = $(CURDIR)

BINDIR := bin
BINARIES := $(addprefix $(BINDIR)/,$(DEB_ARCHES))
PACKAGE_DIR := src/machine-resources
PACKAGE_VENDOR_DIR := $(PACKAGE_DIR)/vendor
GO_CACHE_DIR := $(shell [ -d $(HOME)/.cache ] && echo $(HOME)/.cache/go-cache || mktemp --tmpdir -d $(TMPDIR)tmp.go-cacheXXX)
.DEFAULT_GOAL: build

DEP := cd $(PACKAGE_DIR); dep

.DEFAULT_GOAL := build

build: $(BINARIES)
.PHONY: build

$(BINARIES): $(PACKAGE_VENDOR_DIR) $(PACKAGE_DIR)/main.go
	GOCACHE=$(GO_CACHE_DIR) GOARCH=$(GOARCH_$(notdir $@)) go build -ldflags '-s -w' -o $(CURDIR)/$@ machine-resources

$(PACKAGE_VENDOR_DIR) vendor:
	rm -rf $(PACKAGE_VENDOR_DIR)
	$(DEP) ensure -vendor-only
.PHONY: vendor

clean: DEP_PACKAGES_DIRS = $(filter-out $(PACKAGE_DIR),$(wildcard src/*))
clean:
	rm -rf $(BINDIR) pkg $(DEP_PACKAGES_DIRS) $(PACKAGE_VENDOR_DIR)
.PHONY: clean

update-deps:
	$(DEP) ensure -update
.PHONY: update-deps

install: $(BINARIES)
	install -t $(DESTDIR)/usr/share/maas/machine-resources -D $(BINARIES)
.PHONY: install
