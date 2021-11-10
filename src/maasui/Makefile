MAKEFILE_DIR := $(shell dirname $(realpath $(lastword $(MAKEFILE_LIST))))
NODEJS_DIR := $(MAKEFILE_DIR)/nodejs
NODEJS_BIN := $(NODEJS_DIR)/bin

export PATH := $(NODEJS_BIN):$(PATH)

YARN_TARBALL := nodejs/yarn.tar.gz
NODEJS_TARBALL := nodejs/nodejs.tar.gz

NODEJS_VERSION := 16.13.0
YARN_VERSION := 1.22.17


build: build/index.html
.PHONY: build

clean-build:
	rm -rf build src/build src/ui/dist src/legacy/dist src/shared/dist
.PHONY: clean-build

clean: clean-build
	rm -rf src/node_modules $(NODEJS_DIR)
.PHONY: clean

$(NODEJS_DIR):
	mkdir -p $@

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

src/yarn.lock:
	git submodule update --init --remote

src/build: $(NODEJS_BIN)/yarn src/yarn.lock
	yarn --cwd src build-all

build/index.html: src/build
	mkdir -p build
	cp -R src/build/* build/
