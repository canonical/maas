#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

BASE_DIR := $(shell dirname $(realpath $(lastword $(MAKEFILE_LIST))))
SRC_DIR := $(BASE_DIR)
BUILD_DIR := $(BASE_DIR)/build
NODEJS_DIR := $(BASE_DIR)/nodejs
NODEJS_BIN := $(NODEJS_DIR)/bin

export PATH := $(NODEJS_BIN):$(PATH)

NODEJS_VERSION := 22.21.1
YARN_VERSION := 1.22.22

UNAME_ARCH := $(shell uname -m)
NODEJS_ARCH := $(shell \
        if [ "$(UNAME_ARCH)" = "x86_64" ]; then echo "x64"; \
        elif [ "$(UNAME_ARCH)" = "aarch64" ]; then echo "arm64"; \
        elif [ "$(UNAME_ARCH)" = "ppc64le" ]; then echo "ppc64le"; \
        elif [ "$(UNAME_ARCH)" = "s390x" ]; then echo "s390x"; \
        else echo "unknown"; \
        fi)

UI_REVISION := $(shell git -C $(BASE_DIR) rev-parse HEAD)
TARBALL_NAME := maas_ui_$(UI_REVISION).tgz

.DEFAULT_GOAL := build

build:
	$(MAKE) build-local
.PHONY: build

clean-build:
	rm -rf $(BUILD_DIR)
.PHONY: clean-build

clean: clean-build
	rm -rf $(SRC_DIR)/node_modules $(NODEJS_DIR)
.PHONY: clean

build-local: $(BUILD_DIR)/index.html
.PHONY: build-local

$(NODEJS_BIN)/node:
	@if [ "$(NODEJS_ARCH)" = "unknown" ]; then \
		echo "Unsupported architecture: $(UNAME_ARCH)" 1>&2; \
		exit 1; \
	fi
	curl -sfL https://nodejs.org/dist/v$(NODEJS_VERSION)/node-v$(NODEJS_VERSION)-linux-$(NODEJS_ARCH).tar.xz | tar --recursive-unlink --one-top-level=$(NODEJS_DIR) --strip-components=1 --extract -J
	@touch --no-create $@

$(NODEJS_BIN)/yarn: $(NODEJS_BIN)/node
	curl -sfL https://github.com/yarnpkg/yarn/releases/download/v$(YARN_VERSION)/yarn-v$(YARN_VERSION).tar.gz | tar --one-top-level=$(NODEJS_DIR) --strip-components=1 --extract -z
	@touch --no-create $@

$(BUILD_DIR)/index.html: $(NODEJS_BIN)/yarn $(NODEJS_DIR)
	yarn --cwd $(SRC_DIR) build

$(NODEJS_DIR):
	mkdir -p $@
