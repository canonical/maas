.DEFAULT_GOAL := all
.DELETE_ON_ERROR:

SHELL         := /bin/bash
.SHELLFLAGS   := -euo pipefail -c

GO      	 ?= go
BUILD_DIR  := build
VENDOR_DIR := vendor
BTF_PATH   := /sys/kernel/btf/vmlinux
BPFTOOL    ?= bpftool
GOFLAGS 	 ?= -mod=readonly

# Explicitly set cache dirs to avoid situations where we can't mkdir under $HOME (e.g. Launchpad builds)
GOCACHE_DEFAULT    := $(HOME)/.cache/go-cache
GOMODCACHE_DEFAULT := $(HOME)/go/pkg/mod

export GOCACHE    = $(if $(wildcard $(HOME)/.cache),$(GOCACHE_DEFAULT),$(shell mktemp -d))
export GOMODCACHE = $(if $(wildcard $(HOME)/go),$(GOMODCACHE_DEFAULT),$(shell mktemp -d))

export MAKEDIR      = $(CURDIR)
export GOFLAGS

# Keep track of generated files required for build and test
generated := \
		internal/dhcp/xdp/bpf_bpfeb.go \
		internal/dhcp/xdp/bpf_bpfel.go

# Targets that must NOT trigger code generation
no_generate_targets := clean vendor format

.PHONY: all
all: build

ARTIFACTS := maas-agent maas-netmon

.PHONY: build
build: $(addprefix $(BUILD_DIR)/,$(ARTIFACTS))

$(BUILD_DIR)/maas-agent: export CGO_ENABLED = 1
$(BUILD_DIR)/maas-agent: GO_LDFLAGS = -ldflags '-linkmode=external -extldflags "-static -fPIC -ldqlite -luv -llz4 -lxxhash"'
$(BUILD_DIR)/maas-agent: $(generated)
	$(GO) build $(GO_LDFLAGS) -o $@ ./cmd/maas-agent

$(BUILD_DIR)/maas-netmon: export CGO_ENABLED = 0
$(BUILD_DIR)/maas-netmon:
	$(GO) build -o $@ ./cmd/maas-netmon

.PHONY: install
install: build
	install -t $(DESTDIR)/usr/sbin -D $(addprefix $(BUILD_DIR)/,$(ARTIFACTS))

.PHONY: test
test: $(generated)
	$(GO) test ./...

.PHONY: test-race
test-race: export CGO_ENABLED = 1
test-race: $(generated)
	$(GO) test -race ./...

.PHONY: test-cover
test-cover: $(generated)
	$(GO) test -coverprofile=cover.out ./...

.PHONY: generate
generate: $(generated)
	$(GO) generate ./...

.PHONY: vendor
vendor:
	$(GO) mod tidy
	$(GO) mod verify
	$(GO) mod vendor

internal/ebpf/include/vmlinux.h:
	{ echo "// Generated on $$(uname -srmo) kernel"; \
	  $(BPFTOOL) version | sed 's/^/\/\/ /'; \
	  echo ""; \
	  $(BPFTOOL) btf dump file '$(BTF_PATH)' format c; } > '$@.tmp'
	mv '$@.tmp' '$@'

internal/dhcp/xdp/%_bpfel.go internal/dhcp/xdp/%_bpfeb.go internal/dhcp/xdp/%.go.d &:
	$(GO) generate -x ./internal/dhcp/xdp

.PHONY: clean
clean:
	rm -rf $(BUILD_DIR) $(generated) $(addsuffix .d,$(generated)) cover.out

.PHONY: format
format:
	$(GO) fmt ./...

# Only include generated dependency tracking when not running no-generate targets
ifeq ($(filter $(no_generate_targets),$(MAKECMDGOALS)),)
-include internal/dhcp/xdp/bpf_bpfeb.go.d
-include internal/dhcp/xdp/bpf_bpfel.go.d
endif
