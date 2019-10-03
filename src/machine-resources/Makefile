#
# Makefile to build the machine-resources binary on all relevant platforms.
#

ARCHES := amd64 386 arm arm64 ppc64le s390x

export GOPATH = $(CURDIR)

BINDIR := bin
BINARIES := $(addprefix $(BINDIR)/,$(ARCHES))
PACKAGE_DIR := src/machine-resources
PACKAGE_VENDOR_DIR := $(PACKAGE_DIR)/vendor

.DEFAULT_GOAL: build

build: $(BINARIES)
.PHONY: build

$(BINARIES): $(PACKAGE_VENDOR_DIR)
	GOARCH=$(notdir $@) go build -ldflags '-s -w' -o $@ machine-resources
.PHONY: $(ARCHES)

$(PACKAGE_VENDOR_DIR) vendor:
	rm -rf $(PACKAGE_VENDOR_DIR)
	cd $(PACKAGE_DIR); dep ensure
.PHONY: vendor

clean: DEP_PACKAGES_DIRS = $(filter-out $(PACKAGE_DIR),$(wildcard src/*))
clean:
	rm -rf $(BINDIR) pkg $(DEP_PACKAGES_DIRS) $(PACKAGE_VENDOR_DIR)
.PHONY: clean
