mkfile_dir := $(shell dirname $(realpath $(lastword $(MAKEFILE_LIST))))
nodejs_path := $(mkfile_dir)/nodejs

export PATH := $(nodejs_path)/bin:$(PATH)

build: build/index.html
.PHONY: build

clean-build:
	rm -rf build src/build src/ui/dist src/legacy/dist src/shared/dist
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

src/build: nodejs/bin/yarn src/yarn.lock
	yarn --cwd src build-all

build/index.html: src/build
	mkdir -p build
	cp -R src/build/* build/
