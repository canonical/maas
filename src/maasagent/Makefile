SHELL := /bin/bash

BIN_DIR := bin
BUILD_DIR := build

GO := go # override to use alternative Go binary
VENDOR_DIR := vendor

LDFLAGS := -ldflags '-s -w -extldflags "-static"'

# Explicitly set cache dirs to avoid situations where we can't mkdir under $HOME (e.g. Launchpad builds)
export GOCACHE := $(shell [ -d $(HOME)/.cache ] && echo $(HOME)/.cache/go-cache || mktemp --tmpdir -d tmp.go-cacheXXX)
export GOMODCACHE := $(shell [ -d $(HOME)/go ] && echo $(HOME)/go/pkg/mod || mktemp --tmpdir -d tmp.go-mod-cacheXXX)
export GOFLAGS := -mod=vendor

default: build

$(BIN_DIR): ; mkdir -p $@

ARTIFACTS := $(subst /,,$(subst cmd/,,$(wildcard cmd/*/)))

.PHONY: build
build: vendor $(addprefix $(BUILD_DIR)/,$(ARTIFACTS))

$(BUILD_DIR)/%:
	CGO_ENABLED=0 $(GO) build -o $(BUILD_DIR)/$(OUT_PREFIX)$* $(LDFLAGS) cmd/$*/*.go

.PHONY: install
install: build
	install -t $(DESTDIR)/bin -D $(BUILD_DIR)/*

.PHONY: test
test:
	CGO_ENABLED=1 $(GO) test -race ./...

.PHONY: generate
generate: $(BIN_DIR)/mockgen
	$(GO) generate ./...

.PHONY: tools
tools: $(BIN_DIR)/mockgen

.PHONY: vendor
vendor: $(VENDOR_DIR)/modules.txt

$(VENDOR_DIR)/modules.txt: go.mod
	$(GO) mod vendor

$(BIN_DIR)/mockgen: MOCKGEN_VERSION=1.6.0
$(BIN_DIR)/mockgen: | $(BIN_DIR)
	GOFLAGS="" GOBIN="$(realpath $(dir $@))" $(GO) install github.com/golang/mock/mockgen@v$(MOCKGEN_VERSION)

.PHONY: clean
clean:
	rm -rf $(VENDOR_DIR) $(BIN_DIR) $(BUILD_DIR)
