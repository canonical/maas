mkfile_dir := $(shell dirname $(realpath $(lastword $(MAKEFILE_LIST))))
nodejs_path := $(mkfile_dir)/nodejs

export PATH := $(nodejs_path)/bin:$(PATH)

build: build/ui/index.html build/legacy/index.html
.PHONY: build

clean-build:
	rm -rf build src/build src/ui/build src/legacy/build
.PHONY: clean-build

clean: clean-build
	rm -rf src/node_modules nodejs
.PHONY: clean

nodejs/nodejs.tar.gz:
	mkdir -p nodejs
	wget -O nodejs/nodejs.tar.gz https://nodejs.org/dist/v12.13.0/node-v12.13.0-linux-x64.tar.xz

nodejs/bin/node: nodejs/nodejs.tar.gz
	tar -C nodejs/ -xf nodejs/nodejs.tar.gz --strip-components=1
	@touch --no-create $@

nodejs/yarn.tar.gz:
	mkdir -p nodejs
	wget -O nodejs/yarn.tar.gz https://github.com/yarnpkg/yarn/releases/download/v1.19.1/yarn-v1.19.1.tar.gz

nodejs/bin/yarn: nodejs/bin/node nodejs/yarn.tar.gz
	tar -C nodejs/ -xf nodejs/yarn.tar.gz --strip-components=1
	@touch --no-create $@

src/yarn.lock:
	git submodule update --init --remote

src/shared/dist/index.js: nodejs/bin/yarn src/yarn.lock
	yarn --cwd src build-shared

src/ui/build/index.html: src/shared/dist/index.js
	PUBLIC_URL=/MAAS/r/ yarn --cwd src build-ui

src/legacy/build/index.html: src/shared/dist/index.js
	PUBLIC_URL=/MAAS/ yarn --cwd src build-legacy

src/build: src/ui/build/index.html src/legacy/build/index.html
	yarn --cwd src copy-build

build/ui/index.html: src/build
	mkdir -p build
	cp -R src/build/ui/ build/

build/legacy/index.html: src/build
	mkdir -p build
	cp -R src/build/legacy/ build/
