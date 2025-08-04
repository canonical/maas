.DEFAULT_GOAL := all

SHELL      := /bin/bash
BIN_DIR    := bin
BUILD_DIR  := build
VENDOR_DIR := vendor
BTF_PATH   := /sys/kernel/btf/vmlinux
LDFLAGS    := -ldflags '-linkmode=external -extldflags "-fPIC -static -luv -llz4 -ldqlite"'

GO      ?= go
GOFLAGS ?= -mod=readonly
BPFTOOL ?= bpftool

# Explicitly set cache dirs to avoid situations where we can't mkdir under $HOME (e.g. Launchpad builds)
export GOCACHE     := $(shell [ -d $(HOME)/.cache ] && echo $(HOME)/.cache/go-cache || mktemp --tmpdir -d tmp.go-cacheXXX)
export GOMODCACHE  := $(shell [ -d $(HOME)/go ] && echo $(HOME)/go/pkg/mod || mktemp --tmpdir -d tmp.go-mod-cacheXXX)
export CGO_ENABLED := 1
export MAKEDIR      = $(CURDIR)
export GOFLAGS

ARTIFACTS := $(subst /,,$(subst cmd/,,$(wildcard cmd/*/)))

generated := \
						 internal/dhcp/xdp/bpf_bpfeb.go \
						 internal/dhcp/xdp/bpf_bpfel.go

deps := $(addsuffix .d,$(generated))


.PHONY: all
all: build

.PHONY: build
build: $(generated) $(deps)
	$(GO) env
	$(MAKE) $(addprefix $(BUILD_DIR)/,$(ARTIFACTS))

(BIN_DIR): ; mkdir -p $@

$(BUILD_DIR)/%:
	$(GO) build -o $(BUILD_DIR)/$* $(LDFLAGS) cmd/$*/*.go

.PHONY: install
install: build
	install -d $(DESTDIR)/bin
	install $(addprefix $(BUILD_DIR)/,$(ARTIFACTS)) $(DESTDIR)/bin

.PHONY: test
test: $(generated) $(deps)
	$(GO) test ./...

.PHONY: test-race
test-race:
	$(GO) test -race ./...

.PHONY: test-cover
test-cover: $(generated) $(deps)
	$(GO) test -coverprofile=cover.out ./...

.PHONY: generate
generate:
	$(GO) generate ./...

.PHONY: vendor
vendor:
	$(GO) mod vendor

internal/ebpf/include/vmlinux.h:
	echo "// Generated on $$(uname -srmo) kernel" > $@
	$(BPFTOOL) version | sed 's/^/\/\/ /' >> $@
	echo "" >> $@
	$(BPFTOOL) btf dump file $(BTF_PATH) format c >> $@ || rm $@

internal/dhcp/xdp/%_bpfel.go internal/dhcp/xdp/%_bpfeb.go internal/dhcp/xdp/%.go.d:
	$(GO) generate -x -tags bpf ./internal/dhcp/xdp

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
