.DEFAULT_GOAL := all

SHELL      := /bin/bash
BIN_DIR    := bin
BUILD_DIR  := build
LDFLAGS    := -ldflags '-linkmode=external -extldflags "-fPIC -static"'

GO      ?= go

# Explicitly set cache dirs to avoid situations where we can't mkdir under $HOME (e.g. Launchpad builds)
export GOCACHE     := $(shell [ -d $(HOME)/.cache ] && echo $(HOME)/.cache/go-cache || mktemp --tmpdir -d tmp.go-cacheXXX)
export GOMODCACHE  := $(shell [ -d $(HOME)/go ] && echo $(HOME)/go/pkg/mod || mktemp --tmpdir -d tmp.go-mod-cacheXXX)
export CGO_ENABLED := 1
export MAKEDIR      = $(CURDIR)
export GOFLAGS

ARTIFACTS := maas-openfga maas-openfga-migrator maas-openfga-app-migrator

.PHONY: all
all: build

.PHONY: build
build:
	$(GO) env
	$(MAKE) $(addprefix $(BUILD_DIR)/,$(ARTIFACTS))

(BIN_DIR): ; mkdir -p $@

$(BUILD_DIR)/%: $(generated) $(deps)
	$(GO) build -o $(BUILD_DIR)/$* $(LDFLAGS) ./cmd/$*/*.go

.PHONY: install
install: build
	install -d $(DESTDIR)/bin
	install $(addprefix $(BUILD_DIR)/,$(ARTIFACTS)) $(DESTDIR)/bin

.PHONY: test
test: $(generated) $(deps) build
	$(GO) test ./...

.PHONY: test-cover
test-cover: $(generated) $(deps)
	$(GO) test -coverprofile=cover.out ./...

.PHONY: generate
generate:
	$(GO) generate ./...

.PHONY: vendor
vendor:
	$(GO) mod vendor

.PHONY: clean
clean:
	rm -rf $(VENDOR_DIR) $(BIN_DIR) $(BUILD_DIR)
	git clean -Xdf

.PHONY: format
format:
	$(GO) fmt ./...

ifneq ($(MAKECMDGOALS),clean)
-include $(deps)
endif
