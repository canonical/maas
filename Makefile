python := python3
snapcraft := snapcraft

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

# MAAS SASS stylesheets. The first input file (maas-styles.css) imports
# the others, so is treated specially in the target definitions.
scss_input := src/maasserver/static/scss/build.scss
scss_deps := $(wildcard src/maasserver/static/scss/_*.scss)
scss_output := src/maasserver/static/css/build.css

javascript_deps := \
  $(shell find src -name '*.js' -not -path '*/maasserver/static/js/bundle/*') \
  package.json \
  webpack.config.js \
  yarn.lock

javascript_output := \
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

export PATH := $(nodejs_path):$(PATH)

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
  bin/test.js \
  bin/test.e2e \
  bin/test.parallel \
  bin/py bin/ipy \
  pycharm

all: build doc

# Install all packages required for MAAS development & operation on
# the system. This may prompt for a password.
install-dependencies: release := $(shell lsb_release -c -s)
install-dependencies:
	sudo DEBIAN_FRONTEND=noninteractive apt-get -y \
	    --no-install-recommends install $(shell sort -u \
	        $(addprefix required-packages/,base build dev doc) | sed '/^\#/d')
	sudo DEBIAN_FRONTEND=noninteractive apt-get -y \
	    purge $(shell sort -u required-packages/forbidden | sed '/^\#/d')
	if [ -x /usr/bin/snap ]; then sudo snap install --classic snapcraft; fi

.gitignore:
	sed 's:^[.]/:/:' $^ > $@

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
buildout.cfg: .run .run-e2e

bin/database: bin/buildout buildout.cfg versions.cfg setup.py
	$(buildout) install database
	@touch --no-create $@

bin/test.parallel: \
  bin/buildout buildout.cfg versions.cfg setup.py
	$(buildout) install parallel-test
	@touch --no-create $@

bin/maas-region bin/regiond: \
    bin/buildout buildout.cfg versions.cfg setup.py \
    $(scss_output) $(javascript_output)
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

bin/test.js: bin/karma bin/buildout buildout.cfg versions.cfg setup.py
	$(buildout) install js-test
	@touch --no-create $@

bin/test.e2e: \
    bin/protractor bin/buildout buildout.cfg versions.cfg setup.py
	$(buildout) install e2e-test
	@touch --no-create $@

# bin/maas-region is needed for South migration tests. bin/flake8 is needed for
# checking lint and bin/node-sass is needed for checking css.
bin/test.testing: \
  bin/maas-region bin/flake8 bin/node-sass bin/buildout \
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

bin/sphinx bin/sphinx-build: bin/buildout buildout.cfg versions.cfg setup.py
	$(buildout) install sphinx
	@touch --no-create $@

bin/py bin/ipy: bin/buildout buildout.cfg versions.cfg setup.py
	$(buildout) install repl
	@touch --no-create bin/py bin/ipy

bin/coverage: bin/buildout buildout.cfg versions.cfg setup.py
	$(buildout) install coverage
	@touch --no-create bin/coverage

include/nodejs/bin/node:
	mkdir -p include/nodejs
	wget -O include/nodejs/nodejs.tar.gz https://nodejs.org/dist/v8.9.3/node-v8.9.3-linux-x64.tar.gz
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
  bin/karma
  bin/protractor
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
  karma
  karma-chrome-launcher
  karma-failed-reporter
  karma-firefox-launcher
  karma-jasmine
  karma-ng-html2js-preprocessor
  karma-opera-launcher
  karma-phantomjs-launcher
  karma-sourcemap-loader
  macaroon-bakery
  node-sass
  phantomjs-prebuilt
  prop-types
  protractor
  react
  react-dom
  react2angular
  uglifyjs-webpack-plugin
  vanilla-framework
  vanilla-framework-react
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
  bin/test.js
endef

lxd:
	utilities/configure-lxd-profile
	utilities/create-lxd-bionic-image

test: bin/test.parallel bin/coverage
	@$(RM) .coverage .coverage.*
	@bin/test.parallel --with-coverage --subprocess-per-core
	@bin/coverage combine

test-js: bin/test.js javascript
	@bin/test.js

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

src/maasserver/testing/initial.maas_test.sql: bin/database syncdb
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
    lint-js lint-doc lint-rst
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
	  ! -path '*/migrations/*' ! -path '*/south_migrations/*' -print0 \
	    | xargs -r0 bin/flake8 --config=.flake8

# Ignore tests when checking complexity. The maximum complexity ought to
# be close to 10 but MAAS has many functions that are over that so we
# start with a much higher number. Over time we can ratchet it down.
lint-py-complexity: maximum=26
lint-py-complexity: sources = setup.py src
lint-py-complexity: bin/flake8
	@find $(sources) -name '*.py' \
	  ! -path '*/migrations/*' ! -path '*/south_migrations/*' \
	  ! -path '*/tests/*' ! -path '*/testing/*' ! -name 'testing.py' \
	  -print0 | xargs -r0 bin/flake8 --config=.flake8 --max-complexity=$(maximum)

# Statically check imports against policy.
lint-py-imports: sources = setup.py src
lint-py-imports:
	@utilities/check-imports
	@find $(sources) -name '*.py' \
	  ! -path '*/migrations/*' ! -path '*/south_migrations/*' \
	  -print0 | xargs -r0 utilities/find-early-imports

lint-doc:
	@utilities/doc-lint

# JavaScript lint is checked in parallel for speed.  The -n20 -P4 setting
# worked well on a multicore SSD machine with the files cached, roughly
# doubling the speed, but it may need tuning for slower systems or cold caches.
lint-js: sources = src/maasserver/static/js
lint-js:
	@find $(sources) -type f -not -path '*/angular/3rdparty/*' -a \
		-not -path '*-min.js' -a \
	    '(' -name '*.html' -o -name '*.js' ')' -print0 \
		| xargs -r0 -n20 -P4 $(pocketlint)

# Apply automated formatting to all Python files.
format: sources = $(wildcard *.py contrib/*.py) src utilities etc
format:
	@find $(sources) -name '*.py' -print0 | xargs -r0 utilities/format-imports
	@find src/ -type f -exec file "{}" ";" | grep CRLF | cut -d ':' -f1 | xargs dos2unix

check: clean test

docs/api.rst: bin/maas-region src/maasserver/api/doc_handler.py syncdb
	bin/maas-region generate_api_doc > $@

sampledata: bin/maas-region bin/database syncdb
	$(dbrun) bin/maas-region generate_sample_data

doc: bin/sphinx docs/api.rst
	bin/sphinx

docs/_build/html/index.html: doc

doc-browse: docs/_build/html/index.html
	sensible-browser $< > /dev/null 2>&1 &

doc-with-versions: bin/sphinx docs/api.rst
	$(MAKE) -C docs/_build SPHINXOPTS="-A add_version_switcher=true" html

man: $(patsubst docs/man/%.rst,man/%,$(wildcard docs/man/*.rst))

man/%: docs/man/%.rst | bin/sphinx-build
	bin/sphinx-build -b man docs man $^

.run .run-e2e: run-skel
	@cp --archive --verbose $^ $@

.idea: contrib/pycharm
	@cp --archive --verbose $^ $@

pycharm: .idea

styles: $(scss_output)

force-styles: clean-styles $(scss_output)

$(scss_output): bin/node-sass $(scss_input) $(scss_deps)
	bin/node-sass --include-path=src/maasserver/static/scss \
	    --output-style compressed $(scss_input) -o $(dir $@)

clean-styles:
	$(RM) $(scss_output)

javascript: node_modules $(javascript_output)

force-javascript: clean-javascript node_modules $(javascript_output)

lander-javascript: force-javascript
	git update-index -q --no-assume-unchanged $(strip $(javascript_output)) 2> /dev/null || true
	git add -f $(strip $(javascript_output)) 2> /dev/null || true

lander-styles: force-styles node_modules $(scss_output)
	git update-index -q --no-assume-unchanged $(strip $(scss_output)) 2> /dev/null || true
	git add -f $(strip $(scss_output)) 2> /dev/null || true

# The $(subst ...) uses a pattern rule to ensure Webpack runs just once,
# even if all four output files are out-of-date.
$(subst .,%,$(javascript_output)): $(javascript_deps)
	node_modules/.bin/webpack
	@touch --no-create $(strip $(javascript_output))
	@git update-index -q --assume-unchanged $(strip $(javascript_output)) 2> /dev/null || true

clean-javascript:
	$(RM) -r src/maasserver/static/js/bundle

clean: stop clean-failed
	find . -type f -name '*.py[co]' -print0 | xargs -r0 $(RM)
	find . -type d -name '__pycache__' -print0 | xargs -r0 $(RM) -r
	find . -type f -name '*~' -print0 | xargs -r0 $(RM)
	$(RM) -r media/demo/* media/development media/development.*
	$(RM) src/maasserver/data/templates.py
	$(RM) *.log
	$(RM) docs/api.rst
	$(RM) -r docs/_autosummary docs/_build
	$(RM) -r man/.doctrees
	$(RM) .coverage .coverage.* coverage.xml
	$(RM) -r coverage
	$(RM) -r .hypothesis
	$(RM) -r bin include lib local node_modules
	$(RM) -r eggs develop-eggs
	$(RM) -r build dist logs/* parts
	$(RM) tags TAGS .installed.cfg
	$(RM) -r *.egg *.egg-info src/*.egg-info
	$(RM) -r services/*/supervise
	$(RM) -r .run .run-e2e
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
  clean-javascript
  clean-styles
  configure-buildout
  coverage-report
  dbharness
  distclean
  doc
  doc-browse
  force-styles
  force-javascript
  force-yarn-update
  format
  harness
  install-dependencies
  javascript
  lander-javascript
  lander-styles
  lint
  lint-css
  lint-doc
  lint-js
  lint-py
  lint-py-complexity
  lint-py-imports
  lint-rst
  lxd
  man
  print-%
  sampledata
  smoke
  styles
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
packaging-orig-targz := $(packaging-dir).orig.tar.gz

-packaging-clean:
	rm -rf $(packaging-build-area)
	mkdir -p $(packaging-build-area)

-packaging-export-orig: $(packaging-build-area)
	git archive --format=tar.gz $(packaging-export-extra) \
            --prefix=$(packaging-dir)/ \
	    -o $(packaging-build-area)/$(packaging-orig-targz) HEAD

-packaging-export-orig-uncommitted: $(packaging-build-area)
	git ls-files --others --exclude-standard --cached | grep -v '^debian' | \
	    xargs tar --transform 's,^,$(packaging-dir)/,' -czf $(packaging-build-area)/$(packaging-orig-targz)

-packaging-export: -packaging-export-orig$(if $(export-uncommitted),-uncommitted,)

-package-tree: -packaging-export
	(cd $(packaging-build-area) && tar xfz $(packaging-orig-targz))
	(cp -r debian $(packaging-build-area)/$(packaging-dir))
	echo "maas ($(packaging-version)-0ubuntu1) UNRELEASED; urgency=medium" \
	    > $(tmp_changelog)
	tail -n +2 debian/changelog >> $(tmp_changelog)
	mv $(tmp_changelog) $(packaging-build-area)/$(packaging-dir)/debian/changelog

package: javascript -packaging-clean -package-tree
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

sync-dev-snap: build/dev-snap/prime
	rsync -v --exclude 'maastesting' --exclude 'tests' --exclude 'testing' \
		--exclude '*.pyc' --exclude '__pycache__' -r -u -l -t -W -L \
		src/ build/dev-snap/prime/lib/python3.6/site-packages/
	rsync -v -r -u -l -t -W -L \
		src/maasserver/static/ build/dev-snap/prime/usr/share/maas/web/static/

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
  bin/node-sass
  bin/webpack
  bin/sphinx bin/sphinx-build
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
    install it with 'sudo apt-get install $(2)'))
endef
