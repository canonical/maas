python := python3
snapcraft := SNAPCRAFT_BUILD_INFO=1 /snap/bin/snapcraft

# pkg_resources makes some incredible noise about version numbers. They
# are not indications of bugs in MAAS so we silence them everywhere.
export PYTHONWARNINGS = \
  ignore:You have iterated over the result:RuntimeWarning:pkg_resources:

# Network activity can be suppressed by setting offline=true (or any
# non-empty string) at the command-line.
ifeq ($(offline),)
buildout := bin/buildout
else
buildout := bin/buildout buildout:offline=true
endif

# If offline has been selected, attempt to further block HTTP/HTTPS
# activity by setting bogus proxies in the environment.
ifneq ($(offline),)
export http_proxy := broken
export https_proxy := broken
endif

asset_deps := \
  $(shell find src -name '*.js' -not -path '*/maasserver/static/js/bundle/*') \
  $(shell find src -name '*.scss') \
  package.json \
  webpack.config.js \
  yarn.lock

asset_output := \
  src/maasserver/static/css/build.css \
  src/maasserver/static/js/bundle/maas-min.js \
  src/maasserver/static/js/bundle/maas-min.js.map \
  src/maasserver/static/js/bundle/vendor-min.js \
  src/maasserver/static/js/bundle/vendor-min.js.map

# Prefix commands with this when they need access to the database.
# Remember to add a dependency on bin/database from the targets in
# which those commands appear.
dbrun := bin/database --preserve run --

# Path to install local nodejs.
mkfile_dir := $(shell dirname $(realpath $(lastword $(MAKEFILE_LIST))))
nodejs_path := $(mkfile_dir)/include/nodejs/bin

export GOPATH := $(shell go env GOPATH)
export PATH := $(GOPATH)/bin:$(nodejs_path):$(PATH)

# For things that care, postgresfixture for example, we always want to
# use the "maas" databases.
export PGDATABASE := maas

# For anything we start, we want to hint as to its root directory.
export MAAS_ROOT := $(CURDIR)/.run

build: \
  bin/buildout \
  bin/database \
  bin/maas \
  bin/maas-common \
  bin/maas-rack \
  bin/maas-region \
  bin/rackd \
  bin/regiond \
  bin/test.cli \
  bin/test.rack \
  bin/test.region \
  bin/test.region.legacy \
  bin/test.testing \
  bin/test.parallel \
  bin/py bin/ipy \
  pycharm

all: build doc

REQUIRED_DEPS_FILES = base build dev doc
FORBIDDEN_DEPS_FILES = forbidden

# list package names from a required-packages/ file
list_required = $(shell sort -u required-packages/$1 | sed '/^\#/d')

# Install all packages required for MAAS development & operation on
# the system. This may prompt for a password.
install-dependencies: release := $(shell lsb_release -c -s)
install-dependencies:
	sudo DEBIAN_FRONTEND=noninteractive apt install --no-install-recommends -y \
		$(foreach deps,$(REQUIRED_DEPS_FILES),$(call list_required,$(deps)))
	sudo DEBIAN_FRONTEND=noninteractive apt purge -y \
		$(foreach deps,$(FORBIDDEN_DEPS_FILES),$(call list_required,$(deps)))
	if [ -x /usr/bin/snap ]; then sudo snap install --classic snapcraft; fi

configure-buildout:
	utilities/configure-buildout

sudoers:
	utilities/install-sudoers
	utilities/grant-nmap-permissions

bin/buildout: bootstrap-buildout.py
	@utilities/configure-buildout --quiet
	$(python) bootstrap-buildout.py --allow-site-packages
	@touch --no-create $@  # Ensure it's newer than its dependencies.

# buildout.cfg refers to .run and .run-e2e.
buildout.cfg: .run

bin/database: bin/buildout buildout.cfg versions.cfg setup.py
	$(buildout) install database
	@touch --no-create $@

bin/test.parallel: \
  bin/buildout buildout.cfg versions.cfg setup.py
	$(buildout) install parallel-test
	@touch --no-create $@

bin/maas-region bin/regiond: \
    bin/buildout buildout.cfg versions.cfg setup.py \
    $(asset_output)
	$(buildout) install region
	@touch --no-create $@

bin/test.region: \
  bin/buildout buildout.cfg versions.cfg setup.py \
  bin/maas-region bin/maas-rack bin/maas-common
	$(buildout) install region-test
	@touch --no-create $@

bin/test.region.legacy: \
    bin/buildout buildout.cfg versions.cfg setup.py
	$(buildout) install region-test-legacy
	@touch --no-create $@

bin/maas: bin/buildout buildout.cfg versions.cfg setup.py
	$(buildout) install cli
	@touch --no-create $@

bin/test.cli: bin/buildout buildout.cfg versions.cfg setup.py bin/maas
	$(buildout) install cli-test
	@touch --no-create $@

# bin/flake8 is needed for checking lint and bin/node-sass is needed for
# checking css.
bin/test.testing: \
  bin/flake8 bin/node-sass bin/buildout \
  buildout.cfg versions.cfg setup.py
	$(buildout) install testing-test
	@touch --no-create $@

bin/maas-rack bin/rackd bin/maas-common: \
  bin/buildout buildout.cfg versions.cfg setup.py
	$(buildout) install rack
	@touch --no-create $@

bin/test.rack: \
  bin/buildout buildout.cfg versions.cfg setup.py bin/maas-rack bin/py
	$(buildout) install rack-test
	@touch --no-create $@

bin/flake8: bin/buildout buildout.cfg versions.cfg setup.py
	$(buildout) install flake8
	@touch --no-create $@

bin/py bin/ipy: bin/buildout buildout.cfg versions.cfg setup.py
	$(buildout) install repl
	@touch --no-create bin/py bin/ipy

bin/coverage: bin/buildout buildout.cfg versions.cfg setup.py
	$(buildout) install coverage
	@touch --no-create bin/coverage

include/nodejs/bin/node:
	mkdir -p include/nodejs
	wget -O include/nodejs/nodejs.tar.gz https://nodejs.org/dist/v8.10.0/node-v8.10.0-linux-x64.tar.gz
	tar -C include/nodejs/ -xf include/nodejs/nodejs.tar.gz --strip-components=1

include/nodejs/yarn.tar.gz:
	mkdir -p include/nodejs
	wget -O include/nodejs/yarn.tar.gz https://yarnpkg.com/latest.tar.gz

include/nodejs/bin/yarn: include/nodejs/yarn.tar.gz
	tar -C include/nodejs/ -xf include/nodejs/yarn.tar.gz --strip-components=1
	@touch --no-create $@

bin/yarn: include/nodejs/bin/yarn
	@mkdir -p bin
	ln -sf ../include/nodejs/bin/yarn $@
	@touch --no-create $@

node_modules: include/nodejs/bin/node bin/yarn
	bin/yarn --frozen-lockfile
	@touch --no-create $@

define js_bins
  bin/node-sass
  bin/webpack
endef

$(strip $(js_bins)): node_modules
	ln -sf ../node_modules/.bin/$(notdir $@) $@
	@touch --no-create $@

define node_packages
  @babel/core
  @babel/preset-react
  @babel/preset-es2015
  @types/prop-types
  @types/react
  @types/react-dom
  babel-polyfill
  babel-loader@^8.0.0-beta.0
  glob
  jasmine-core@=2.99.1
  macaroon-bakery
  node-sass
  prop-types
  react
  react-dom
  react2angular
  vanilla-framework
  webpack
  webpack-cli
  webpack-merge
endef

force-yarn-update: bin/yarn
	$(RM) package.json yarn.lock
	bin/yarn add -D $(strip $(node_packages))

define test-scripts
  bin/test.cli
  bin/test.rack
  bin/test.region
  bin/test.region.legacy
  bin/test.testing
endef

lxd:
	utilities/configure-lxd-profile
	utilities/create-lxd-bionic-image

test: bin/test.parallel bin/coverage
	@$(RM) .coverage .coverage.*
	@bin/test.parallel --with-coverage --subprocess-per-core
	@bin/coverage combine
	$(MAKE) test-js

test-js: assets
	bin/yarn test

test-js-watch: assets
	bin/yarn test --watch

test-serial: $(strip $(test-scripts))
	@bin/maas-region makemigrations --dry-run --exit && exit 1 ||:
	@$(RM) .coverage .coverage.* .failed
	$(foreach test,$^,$(test-template);)
	@test ! -f .failed

test-failed: $(strip $(test-scripts))
	@bin/maas-region makemigrations --dry-run --exit && exit 1 ||:
	@$(RM) .coverage .coverage.* .failed
	$(foreach test,$^,$(test-template-failed);)
	@test ! -f .failed

clean-failed:
	$(RM) .noseids

src/maasserver/testing/initial.maas_test.sql: bin/maas-region bin/database
  # Run migrations without any triggers created.
	$(dbrun) bin/maas-region dbupgrade --internal-no-triggers
	# Data migration will create a notification, that will break tests. Want the
	# database to be a clean schema.
	$(dbrun) bin/maas-region shell -c "from maasserver.models.notification import Notification; Notification.objects.all().delete()"
	bin/database --preserve run -- \
	    pg_dump maas --no-owner --no-privileges \
	        --format=plain > $@

test-initial-data: src/maasserver/testing/initial.maas_test.sql

define test-template
$(test) --with-xunit --xunit-file=xunit.$(notdir $(test)).xml || touch .failed
endef

define test-template-failed
  $(test) --with-xunit --xunit-file=xunit.$(notdir $(test)).xml --failed || \
  $(test) --with-xunit --xunit-file=xunit.$(notdir $(test)).xml --failed || \
  touch .failed
endef

smoke: lint bin/maas-region bin/test.rack
	@bin/maas-region makemigrations --dry-run --exit && exit 1 ||:
	@bin/test.rack --stop

test-serial+coverage: export NOSE_WITH_COVERAGE = 1
test-serial+coverage: test-serial

coverage-report: coverage/index.html
	sensible-browser $< > /dev/null 2>&1 &

coverage.xml: bin/coverage .coverage
	bin/coverage xml -o $@

coverage/index.html: revno = $(or $(shell git rev-parse HEAD 2>/dev/null),???)
coverage/index.html: bin/coverage .coverage
	@$(RM) -r $(@D)
	bin/coverage html \
	    --title "Coverage for MAAS rev $(revno)" \
	    --directory $(@D)

.coverage:
	@$(error Use `$(MAKE) test` to generate coverage)

lint: \
    lint-py lint-py-complexity lint-py-imports \
    lint-js lint-rst lint-go
        # Only Unix line ends should be accepted
	@find src/ -type f -exec file "{}" ";" | \
	    awk '/CRLF/ { print $0; count++ } END {exit count}' || \
	    (echo "Lint check failed; run make format to fix DOS linefeeds."; false)

pocketlint = $(call available,pocketlint,python-pocket-lint)

# XXX jtv 2014-02-25: Clean up this lint, then make it part of "make lint".
lint-css: sources = src/maasserver/static/css
lint-css:
	@find $(sources) -type f \
	    -print0 | xargs -r0 $(pocketlint) --max-length=120

# Python lint checks are time-intensive, but flake8 now knows how to run
# parallel jobs, and does so by default.
lint-py: sources = setup.py src
lint-py: bin/flake8
	@find $(sources) -name '*.py' \
	  ! -path '*/migrations/*' -print0 | xargs -r0 bin/flake8 --config=.flake8

# Ignore tests when checking complexity. The maximum complexity ought to
# be close to 10 but MAAS has many functions that are over that so we
# start with a much higher number. Over time we can ratchet it down.
lint-py-complexity: maximum=26
lint-py-complexity: sources = setup.py src
lint-py-complexity: bin/flake8
	@find $(sources) -name '*.py' \
	  ! -path '*/migrations/*' \
	  ! -path '*/tests/*' ! -path '*/testing/*' ! -name 'testing.py' \
	  -print0 | xargs -r0 bin/flake8 --config=.flake8 --max-complexity=$(maximum)

# Statically check imports against policy.
lint-py-imports: sources = setup.py src
lint-py-imports:
	@utilities/check-imports
	@find $(sources) -name '*.py' \
	  ! -path '*/migrations/*' \
	  -print0 | xargs -r0 utilities/find-early-imports

# JavaScript lint is checked in parallel for speed.  The -n20 -P4 setting
# worked well on a multicore SSD machine with the files cached, roughly
# doubling the speed, but it may need tuning for slower systems or cold caches.
lint-js: sources = src/maasserver/static/js
lint-js:
	@find $(sources) -type f -not -path '*/angular/3rdparty/*' -a \
		-not -path '*-min.js' -a \
	    '(' -name '*.html' -o -name '*.js' ')' -print0 \
		| xargs -r0 -n20 -P4 $(pocketlint)
		bin/yarn lint
		bin/yarn prettier-check

# Go fmt
lint-go:
	@find src/ -name '*.go' -execdir gofmt -l {} + | tee /tmp/gofmt.lint
	@test ! -s /tmp/gofmt.lint

format.parallel:
	@$(MAKE) -s -j format

# Apply automated formatting to all Python, Sass and Javascript files.
format: format-imports format-lineendings format-js format-go

format-imports: sources = $(wildcard *.py contrib/*.py) src utilities etc
format-imports:
	@find $(sources) -name '*.py' -print0 | xargs -r0 utilities/format-imports

# TODO: This should be done in .gitattributes
format-lineendings:
	@find src/ -type f -exec file "{}" ";" | grep CRLF | cut -d ':' -f1 | xargs dos2unix


format-js: bin/yarn
	@bin/yarn -s prettier --loglevel warn

format-go:
	@find src/ -name '*.go' -execdir go fmt {} +

check: clean test

api-docs.rst: bin/maas-region src/maasserver/api/doc_handler.py syncdb
	bin/maas-region generate_api_doc > $@

sampledata: bin/maas-region bin/database syncdb
	$(dbrun) bin/maas-region generate_sample_data

doc: api-docs.rst

.run .run-e2e: run-skel
	@cp --archive --verbose $^ $@

.idea: contrib/pycharm
	@cp --archive --verbose $^ $@

pycharm: .idea

assets: node_modules $(asset_output)

force-assets: clean-assets node_modules $(asset_output)

lander-javascript: force-assets
	git update-index -q --no-assume-unchanged $(strip $(asset_output)) 2> /dev/null || true
	git add -f $(strip $(asset_output)) 2> /dev/null || true

lander-styles: lander-javascript

# The $(subst ...) uses a pattern rule to ensure Webpack runs just once,
# even if all four output files are out-of-date.
$(subst .,%,$(asset_output)): node_modules $(asset_deps)
	bin/yarn build
	@touch --no-create $(strip $(asset_output))
	@git update-index -q --assume-unchanged $(strip $(asset_output)) 2> /dev/null || true

clean-assets:
	$(RM) -r src/maasserver/static/js/bundle
	$(RM)  -r src/maasserver/static/css

watch-assets:
	bin/yarn watch

clean: stop clean-failed clean-assets
	find . -type f -name '*.py[co]' -print0 | xargs -r0 $(RM)
	find . -type d -name '__pycache__' -print0 | xargs -r0 $(RM) -r
	find . -type f -name '*~' -print0 | xargs -r0 $(RM)
	$(RM) -r media/demo/* media/development media/development.*
	$(RM) src/maasserver/data/templates.py
	$(RM) *.log
	$(RM) api-docs.rst
	$(RM) .coverage .coverage.* coverage.xml
	$(RM) -r coverage
	$(RM) -r .hypothesis
	$(RM) -r bin include lib local node_modules
	$(RM) -r eggs develop-eggs
	$(RM) -r build dist logs/* parts
	$(RM) tags TAGS .installed.cfg
	$(RM) -r *.egg *.egg-info src/*.egg-info
	$(RM) -r services/*/supervise
	$(RM) -r .run
	$(RM) -r .idea
	$(RM) xunit.*.xml
	$(RM) .failed

clean+db: clean
	while fuser db --kill -TERM; do sleep 1; done
	$(RM) -r db
	$(RM) .db.lock

distclean: clean
	$(warning 'distclean' is deprecated; use 'clean')

harness: bin/maas-region bin/database
	$(dbrun) bin/maas-region shell \
	  --settings=maasserver.djangosettings.demo

dbharness: bin/database
	bin/database --preserve shell

syncdb: bin/maas-region bin/database
	$(dbrun) bin/maas-region dbupgrade

define phony_targets
  build
  check
  clean
  clean+db
  clean-failed
  clean-assets
  configure-buildout
  coverage-report
  dbharness
  distclean
  doc
  force-assets
  force-yarn-update
  format
  format.parallel
  format-go
  format-imports
  format-lineendings
  format-js
  harness
  install-dependencies
  assets
  lander-javascript
  lander-styles
  lint
  lint-css
  lint-go
  lint-js
  lint-py
  lint-py-complexity
  lint-py-imports
  lint-rst
  lxd
  print-%
  sampledata
  smoke
  sudoers
  syncdb
  sync-dev-snap
  test
  test+lxd
  test-failed
  test-initial-data
  test-serial
  test-serial+coverage
endef

#
# Development services.
#

service_names_region := database dns regiond reloader
service_names_rack := http rackd reloader
service_names_all := $(service_names_region) $(service_names_rack)

# The following template is intended to be used with `call`, and it
# accepts a single argument: a target name. The target name must
# correspond to a service action (see "Pseudo-magic targets" below). A
# region- and rack-specific variant of the target will be created, in
# addition to the target itself. These can be used to apply the service
# action to the region services, the rack services, or all services, at
# the same time.
define service_template
$(1)-region: $(patsubst %,services/%/@$(1),$(service_names_region))
$(1)-rack: $(patsubst %,services/%/@$(1),$(service_names_rack))
$(1): $(1)-region $(1)-rack
phony_services_targets += $(1)-region $(1)-rack $(1)
endef

# Expand out aggregate service targets using `service_template`.
$(eval $(call service_template,pause))
$(eval $(call service_template,restart))
$(eval $(call service_template,start))
$(eval $(call service_template,status))
$(eval $(call service_template,stop))
$(eval $(call service_template,supervise))

# The `run` targets do not fit into the mould of the others.
run-region:
	@services/run $(service_names_region)
run-rack:
	@services/run $(service_names_rack)
run:
	@services/run $(service_names_all)

phony_services_targets += run-region run-rack run

phony_services_targets += run+regiond

# Convenient variables and functions for service control.

setlock = $(call available,setlock,daemontools)
supervise = $(call available,supervise,daemontools)
svc = $(call available,svc,daemontools)
svok = $(call available,svok,daemontools)
svstat = $(call available,svstat,daemontools)

service_lock = $(setlock) -n /run/lock/maas.dev.$(firstword $(1))

# Pseudo-magic targets for controlling individual services.

services/%/@run: services/%/@stop services/%/@deps
	@$(call service_lock, $*) services/$*/run

services/%/@start: services/%/@supervise
	@$(svc) -u $(@D)

services/%/@pause: services/%/@supervise
	@$(svc) -d $(@D)

services/%/@status:
	@$(svstat) $(@D)

services/%/@restart: services/%/@supervise
	@$(svc) -du $(@D)

services/%/@stop:
	@if $(svok) $(@D); then $(svc) -dx $(@D); fi
	@while $(svok) $(@D); do sleep 0.1; done

services/%/@supervise: services/%/@deps
	@mkdir -p logs/$*
	@touch $(@D)/down
	@if ! $(svok) $(@D); then \
	    logdir=$(CURDIR)/logs/$* \
	        $(call service_lock, $*) $(supervise) $(@D) & fi
	@while ! $(svok) $(@D); do sleep 0.1; done

# Dependencies for individual services.

services/dns/@deps: bin/py bin/maas-common

services/database/@deps: bin/database

services/http/@deps: bin/py

services/rackd/@deps: bin/rackd bin/maas-rack bin/maas-common

services/reloader/@deps:

services/regiond/@deps: bin/maas-region bin/maas-rack bin/maas-common

#
# Package building
#

# This ought to be as simple as using
#   gbp buildpackage --git-debian-branch=packaging
# but it is not: without investing more time, we manually pre-build the source
# tree and run debuild.

packaging-repo = https://git.launchpad.net/maas/
packaging-branch = "packaging"

packaging-build-area := $(abspath ../build-area)
packaging-version = $(shell \
    utilities/calc-snap-version | sed s/[-]snap//)
tmp_changelog := $(shell tempfile)
packaging-dir := maas_$(packaging-version)
packaging-orig-tar := $(packaging-dir).orig.tar
packaging-orig-targz := $(packaging-dir).orig.tar.gz

-packaging-clean:
	rm -rf $(packaging-build-area)
	mkdir -p $(packaging-build-area)

-packaging-export-orig: $(packaging-build-area)
	git archive --format=tar $(packaging-export-extra) \
            --prefix=$(packaging-dir)/ \
	    -o $(packaging-build-area)/$(packaging-orig-tar) HEAD
	(cd src/machine-resources && ${MAKE} deps)
	(export GOPATH=$(CURDIR):$(GOPATH) && cd src/machine-resources && ${MAKE} vendor)
	tar -rf $(packaging-build-area)/$(packaging-orig-tar) src/machine-resources/vendor \
		--transform 's,^,$(packaging-dir)/,'
	gzip -f $(packaging-build-area)/$(packaging-orig-tar)

-packaging-export-orig-uncommitted: $(packaging-build-area)
	git ls-files --others --exclude-standard --cached | grep -v '^debian' | \
	    xargs tar --transform 's,^,$(packaging-dir)/,' -cf $(packaging-build-area)/$(packaging-orig-tar)
	(cd src/machine-resources && ${MAKE} deps)
	(export GOPATH=$(CURDIR):$(GOPATH) && cd src/machine-resources && ${MAKE} vendor)
	tar -rf $(packaging-build-area)/$(packaging-orig-tar) src/machine-resources/vendor \
		--transform 's,^,$(packaging-dir)/,'
	gzip -f $(packaging-build-area)/$(packaging-orig-tar)

-packaging-export: -packaging-export-orig$(if $(export-uncommitted),-uncommitted,)

-package-tree: -packaging-export
	(cd $(packaging-build-area) && tar xfz $(packaging-orig-targz))
	(cp -r debian $(packaging-build-area)/$(packaging-dir))
	echo "maas ($(packaging-version)-0ubuntu1) UNRELEASED; urgency=medium" \
	    > $(tmp_changelog)
	tail -n +2 debian/changelog >> $(tmp_changelog)
	mv $(tmp_changelog) $(packaging-build-area)/$(packaging-dir)/debian/changelog

package: assets -packaging-clean -package-tree
	(cd $(packaging-build-area)/$(packaging-dir) && debuild -uc -us)
	@echo Binary packages built, see $(packaging-build-area).

# To build binary packages from uncommitted changes call "make package-dev".
package-dev:
	make export-uncommitted=yes package

source-package: -package-tree
	(cd $(packaging-build-area)/$(packaging-dir) && debuild -S -uc -us)
	@echo Source package built, see $(packaging-build-area).

# To build source packages from uncommitted changes call "make package-dev".
source-package-dev:
	make export-uncommitted=yes source-package

# To rebuild packages (i.e. from a clean slate):
package-rebuild: package-clean package

package-dev-rebuild: package-clean package-dev

source-package-rebuild: source-package-clean source-package

source-package-dev-rebuild: source-package-clean source-package-dev

# To clean built packages away:
package-clean: patterns := *.deb *.udeb *.dsc *.build *.changes
package-clean: patterns += *.debian.tar.xz *.orig.tar.gz
package-clean:
	@$(RM) -v $(addprefix $(packaging-build-area)/,$(patterns))

source-package-clean: patterns := *.dsc *.build *.changes
source-package-clean: patterns += *.debian.tar.xz *.orig.tar.gz
source-package-clean:
	@$(RM) -v $(addprefix $(packaging-build-area)/,$(patterns))


# Debugging target. Allows printing of any variable.
# As an example, try:
#     make print-scss_input
print-%:
	@echo $* = $($*)

define phony_package_targets
  -packaging-export-orig
  -packaging-export-orig-uncommitted
  -packaging-export
  -packaging-fetch
  -packaging-pull
  -packaging-refresh
  -package-tree
  package
  package-clean
  package-dev
  package-dev-rebuild
  package-rebuild
  source-package
  source-package-clean
  source-package-dev
  source-package-dev-rebuild
  source-package-rebuild
endef

#
# Snap building
#

snap-clean:
	$(snapcraft) clean

snap:
	$(snapcraft)

define phony_snap_targets
	snap
	snap-clean
endef


#
# Helpers for using the snap for development testing.
#


build/dev-snap: ## Check out a clean version of the working tree.
	git checkout-index -a --prefix build/dev-snap/

build/dev-snap/prime: build/dev-snap
	cd build/dev-snap && $(snapcraft) prime --destructive-mode

sync-dev-snap: RSYNC=rsync -v -r -u -l -t -W -L
sync-dev-snap: build/dev-snap/prime
	$(RSYNC) --exclude 'maastesting' --exclude 'tests' --exclude 'testing' \
		--exclude '*.pyc' --exclude '__pycache__' \
		src/ build/dev-snap/prime/lib/python3.6/site-packages/
	$(RSYNC) \
		src/maasserver/static/ build/dev-snap/prime/usr/share/maas/web/static/
	$(RSYNC) \
		snap/local/bin/ build/dev-snap/prime/bin/
	$(RSYNC) \
		snap/local/bind/ build/dev-snap/prime/usr/share/maas/bind
	$(RSYNC) \
		snap/local/conf/ build/dev-snap/prime/usr/share/maas/
	$(RSYNC) \
		snap/local/nginx/ build/dev-snap/prime/usr/share/maas/nginx/

#
# Phony stuff.
#

define phony
  $(phony_package_targets)
  $(phony_services_targets)
  $(phony_snap_targets)
  $(phony_targets)
endef

phony := $(sort $(strip $(phony)))

.PHONY: $(phony) FORCE

#
# Secondary stuff.
#
# These are intermediate files that we want to keep around in the event
# that they get built. By declaring them here we're also telling Make
# that their absense is okay if a rule target is newer than the rule's
# other prerequisites; i.e. don't build them.
#
# For example, converting foo.scss to foo.css might require bin/node-sass. If
# foo.css is newer than foo.scss we know that we don't need to perform that
# conversion, and hence don't need bin/node-sass. We declare bin/node-sass as
# secondary so that Make knows this too.
#

define secondary_binaries
  bin/py bin/buildout
endef

secondary = $(sort $(strip $(secondary_binaries)))

.SECONDARY: $(secondary)

#
# Functions.
#

# Check if a command is found on PATH. Raise an error if not, citing
# the package to install. Return the command otherwise.
# Usage: $(call available,<command>,<package>)
define available
  $(if $(shell which $(1)),$(1),$(error $(1) not found; \
    install it with 'sudo apt install $(2)'))
endef
