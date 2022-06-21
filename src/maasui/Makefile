MAKEFILE_DIR := $(shell dirname $(realpath $(lastword $(MAKEFILE_LIST))))
NODEJS_DIR := $(MAKEFILE_DIR)/nodejs
NODEJS_BIN := $(NODEJS_DIR)/bin
TARBALLS_DIR := $(MAKEFILE_DIR)/tarballs

export PATH := $(NODEJS_BIN):$(PATH)

YARN_TARBALL := nodejs/yarn.tar.gz
NODEJS_TARBALL := nodejs/nodejs.tar.gz

NODEJS_VERSION := 16.13.0
YARN_VERSION := 1.22.17

UI_REVISION := $(shell git -C src/ rev-parse HEAD)
TARBALL_NAME := maas-ui-$(UI_REVISION).tar.gz
TARBALL_FILE := $(TARBALLS_DIR)/$(TARBALL_NAME)

build:
	$(MAKE) fetch-build || $(MAKE) build-local
.PHONY: build

clean-build:
	rm -rf build src/build src/ui/dist src/legacy/dist src/shared/dist
.PHONY: clean-build

clean: clean-build
	rm -rf src/node_modules $(NODEJS_DIR) $(TARBALLS_DIR)
.PHONY: clean

# fetch prebuilt UI

fetch-build: $(TARBALL_FILE)
	rm -rf build
	mkdir -p build
	tar xf $(TARBALL_FILE) -C build
.PHONY: fetch-build

$(TARBALL_FILE): $(TARBALLS_DIR)
	wget -nv -o $@ https://assets.ubuntu.com/v1/$(TARBALL_NAME)

# build UI locally

build-local: build/index.html
.PHONY: build-local

$(NODEJS_TARBALL): $(NODEJS_DIR)
	wget -nv -O $(NODEJS_TARBALL) https://nodejs.org/dist/v$(NODEJS_VERSION)/node-v$(NODEJS_VERSION)-linux-x64.tar.xz

$(NODEJS_BIN)/node: $(NODEJS_TARBALL)
	tar -C $(NODEJS_DIR) -xf $< --strip-components=1
	@touch --no-create $@

$(YARN_TARBALL): $(NODEJS_DIR)
	wget -nv -O $@ https://github.com/yarnpkg/yarn/releases/download/v$(YARN_VERSION)/yarn-v$(YARN_VERSION).tar.gz

$(NODEJS_BIN)/yarn: $(YARN_TARBALL) $(NODEJS_BIN)/node
	tar -C $(NODEJS_DIR) -xf $< --strip-components=1
	@touch --no-create $@

src/yarn.lock:
	git submodule update --init --remote

src/build: $(NODEJS_BIN)/yarn src/yarn.lock
	yarn --cwd src build

build/index.html: src/build
	mkdir -p build
	cp -R src/build/* build/

$(NODEJS_DIR) $(TARBALLS_DIR):
	mkdir -p $@
