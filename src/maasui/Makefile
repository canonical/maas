BASE_DIR := $(shell dirname $(realpath $(lastword $(MAKEFILE_LIST))))
SRC_DIR := $(BASE_DIR)/src
BUILD_DIR := $(BASE_DIR)/build
NODEJS_DIR := $(BASE_DIR)/nodejs
NODEJS_BIN := $(NODEJS_DIR)/bin
TARBALLS_DIR := $(BASE_DIR)/tarballs

export PATH := $(NODEJS_BIN):$(PATH)

YARN_TARBALL := nodejs/yarn.tar.gz
NODEJS_TARBALL := nodejs/nodejs.tar.gz

NODEJS_VERSION := 16.13.0
YARN_VERSION := 1.22.17

UI_REVISION := $(shell git -C $(SRC_DIR) rev-parse HEAD)
TARBALL_NAME := maas-ui-$(UI_REVISION).tar.gz
TARBALL_FILE := $(TARBALLS_DIR)/$(TARBALL_NAME)

.DEFAULT_GOAL := build

build:
	$(MAKE) fetch-build || $(MAKE) build-local
.PHONY: build

clean-build:
	rm -rf $(BUILD_DIR) $(SRC_DIR)/build
.PHONY: clean-build

clean: clean-build
	rm -rf $(SRC_DIR)/node_modules $(NODEJS_DIR) $(TARBALLS_DIR)
.PHONY: clean

# fetch prebuilt UI

fetch-build: $(TARBALL_FILE)
	rm -rf $(BUILD_DIR)
	$(MAKE) $(BUILD_DIR)
	tar xf $(TARBALL_FILE) -C $(BUILD_DIR)
.PHONY: fetch-build

$(TARBALL_FILE): $(TARBALLS_DIR)
	wget -O $@ https://assets.ubuntu.com/v1/$(TARBALL_NAME) || (rm -f $(TARBALL_FILE); exit 1)

# build UI locally

build-local: $(BUILD_DIR)/index.html
.PHONY: build-local

$(NODEJS_TARBALL): $(NODEJS_DIR)
	wget -O $(NODEJS_TARBALL) https://nodejs.org/dist/v$(NODEJS_VERSION)/node-v$(NODEJS_VERSION)-linux-x64.tar.xz

$(NODEJS_BIN)/node: $(NODEJS_TARBALL)
	tar -C $(NODEJS_DIR) -xf $< --strip-components=1
	@touch --no-create $@

$(YARN_TARBALL): $(NODEJS_DIR)
	wget -O $@ https://github.com/yarnpkg/yarn/releases/download/v$(YARN_VERSION)/yarn-v$(YARN_VERSION).tar.gz

$(NODEJS_BIN)/yarn: $(YARN_TARBALL) $(NODEJS_BIN)/node
	tar -C $(NODEJS_DIR) -xf $< --strip-components=1
	@touch --no-create $@

$(SRC_DIR)/yarn.lock:
	git submodule update --init --remote

$(SRC_DIR)/build: $(NODEJS_BIN)/yarn $(SRC_DIR)/yarn.lock
	yarn --cwd $(SRC_DIR) build

$(BUILD_DIR)/index.html: $(BUILD_DIR) $(SRC_DIR)/build
	cp -a $(SRC_DIR)/build/* $(BUILD_DIR)

$(BUILD_DIR) $(NODEJS_DIR) $(TARBALLS_DIR):
	mkdir -p $@
