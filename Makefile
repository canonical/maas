python := python3
snapcraft := SNAPCRAFT_BUILD_INFO=1 /snap/bin/snapcraft

VENV := .ve

# PPA used by MAAS dependencies. It can be overridden by the env.
#
# This uses an explicit empty check (rather than ?=) since Jenkins defines
# variables for parameters even when not passed.
ifeq ($(MAAS_PPA),)
	MAAS_PPA = ppa:maas/2.9
endif

# pkg_resources makes some incredible noise about version numbers. They
# are not indications of bugs in MAAS so we silence them everywhere.
export PYTHONWARNINGS = \
  ignore:You have iterated over the result:RuntimeWarning:pkg_resources:

# If offline has been selected, attempt to further block HTTP/HTTPS
# activity by setting bogus proxies in the environment.
ifneq ($(offline),)
export http_proxy := broken
export https_proxy := broken
endif

# Prefix commands with this when they need access to the database.
# Remember to add a dependency on bin/database from the targets in
# which those commands appear.
dbrun := bin/database --preserve run --

# For anything we start, we want to hint as to its root and data directories.
export MAAS_ROOT := $(CURDIR)/.run
export MAAS_DATA := $(CURDIR)/.run/maas
# For things that care, postgresfixture for example, we always want to
# use the "maas" databases.
export PGDATABASE := maas

# Check if a command is found on PATH. Raise an error if not, citing
# the package to install. Return the command otherwise.
# Usage: $(call available,<command>,<package>)
define available
  $(if $(shell which $(1)),$(1),$(error $(1) not found; \
    install it with 'sudo apt install $(2)'))
endef

.DEFAULT_GOAL := build

define BIN_SCRIPTS
bin/black \
bin/coverage \
bin/flake8 \
bin/isort \
bin/maas \
bin/maas-common \
bin/maas-rack \
bin/maas-region \
bin/maas-power \
bin/postgresfixture \
bin/rackd \
bin/regiond \
bin/subunit-1to2 \
bin/subunit2junitxml \
bin/subunit2pyunit \
bin/test.cli \
bin/test.parallel \
bin/test.rack \
bin/test.region \
bin/test.region.legacy \
bin/test.testing
endef

define PY_SOURCES
src/apiclient \
src/maascli \
src/maasserver \
src/maastesting \
src/metadataserver \
src/provisioningserver \
utilities/release-upload
endef

UI_BUILD := src/maasui/build

OFFLINE_DOCS := src/maas-offline-docs/src

build: \
  .run \
  $(VENV) \
  $(BIN_SCRIPTS) \
  bin/shellcheck \
  bin/py \
  pycharm
.PHONY: build

all: build ui machine-resources doc
.PHONY: all

REQUIRED_DEPS_FILES = base build dev doc
FORBIDDEN_DEPS_FILES = forbidden

# list package names from a required-packages/ file
list_required = $(shell sort -u required-packages/$1 | sed '/^\#/d')

# Install all packages required for MAAS development & operation on
# the system. This may prompt for a password.
install-dependencies: release := $(shell lsb_release -c -s)
install-dependencies: apt_install := sudo DEBIAN_FRONTEND=noninteractive apt install --no-install-recommends -y
install-dependencies:
	$(apt_install) software-properties-common gpg-agent
	if [ -n "$(MAAS_PPA)" ]; then sudo apt-add-repository -y $(MAAS_PPA); fi
	$(apt_install) $(foreach deps,$(REQUIRED_DEPS_FILES),$(call list_required,$(deps)))
	sudo DEBIAN_FRONTEND=noninteractive apt purge -y \
		$(foreach deps,$(FORBIDDEN_DEPS_FILES),$(call list_required,$(deps)))
	if [ -x /usr/bin/snap ]; then cat required-packages/snaps | xargs -L1 sudo snap install; fi
.PHONY: install-dependencies

sudoers:
	utilities/install-sudoers
	utilities/grant-nmap-permissions
.PHONY: sudoers

$(VENV): requirements-dev.txt
	python3 -m venv --system-site-packages --clear $@
	$(VENV)/bin/pip install -r $<

bin:
	mkdir $@

$(BIN_SCRIPTS): $(VENV) bin
	ln -sf ../$(VENV)/$@ $@

bin/py: $(VENV) bin
	ln -sf ../$(VENV)/bin/ipython3 $@

bin/database: bin/postgresfixture
	ln -sf $(notdir $<) $@

bin/shellcheck: URL := "https://github.com/koalaman/shellcheck/releases/download/stable/shellcheck-stable.linux.x86_64.tar.xz"
bin/shellcheck:
	curl -s -L --output - $(URL) | tar xJ --strip=1 -C bin shellcheck-stable/shellcheck

ui: $(UI_BUILD)
.PHONY: ui

$(UI_BUILD):
	$(MAKE) -C src/maasui build

$(OFFLINE_DOCS):
	$(MAKE) -C src/maas-offline-docs

machine-resources-vendor:
	$(MAKE) -C src/machine-resources vendor
.PHONY: machine-resources-vendor

machine-resources: machine-resources-vendor
	$(MAKE) -C src/machine-resources build
.PHONY: machine-resources

define test-scripts
  bin/test.cli
  bin/test.rack
  bin/test.region
  bin/test.region.legacy
  bin/test.testing
endef

test: test-py
.PHONY: test

test-py: bin/test.parallel bin/coverage bin/subunit-1to2 bin/subunit2junitxml bin/subunit2pyunit
	@$(RM) .coverage .coverage.* junit.xml
	@bash -o pipefail -c 'bin/test.parallel --with-coverage --subprocess-per-core --emit-subunit | bin/subunit-1to2 | bin/subunit2junitxml --no-passthrough -f -o junit.xml | bin/subunit2pyunit --no-passthrough'
	@bin/coverage combine
.PHONY: test-py

clean-failed:
	$(RM) .noseids
.PHONY: clean-failed

src/maasserver/testing/initial.maas_test.sql: bin/maas-region bin/database
    # Run migrations without any triggers created.
	$(dbrun) bin/maas-region dbupgrade --internal-no-triggers
    # Data migration will create a notification, that will break tests. Want
    # the database to be a clean schema.
	$(dbrun) bin/maas-region shell -c "from maasserver.models.notification import Notification; Notification.objects.all().delete()"
	$(dbrun) pg_dump maas --no-owner --no-privileges --format=plain > $@

coverage-report: coverage/index.html
	sensible-browser $< > /dev/null 2>&1 &
.PHONY: coverage-report

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

lint: lint-py lint-py-imports lint-py-linefeeds lint-go lint-shell
.PHONY: lint

lint-py: sources = $(wildcard *.py contrib/*.py) $(PY_SOURCES) utilities etc
lint-py: bin/flake8 bin/black bin/isort
	@bin/isort --check-only --diff --recursive $(sources)
	@bin/black $(sources) --check
	@bin/flake8 $(sources)
.PHONY: lint-py

# Statically check imports against policy.
lint-py-imports: sources = setup.py $(PY_SOURCES)
lint-py-imports:
	@utilities/check-imports
.PHONY: lint-py-imports

# Only Unix line ends should be accepted
lint-py-linefeeds:
	@find src/ -name \*.py -exec file "{}" ";" | \
	    awk '/CRLF/ { print $0; count++ } END {exit count}' || \
	    (echo "Lint check failed; run make format to fix DOS linefeeds."; false)
.PHONY: lint-py-linefeeds

# Go fmt
lint-go:
	@find src/ \( -name pkg -o -name vendor \) -prune -o -name '*.go' -exec gofmt -l {} + | \
		tee /tmp/gofmt.lint
	@test ! -s /tmp/gofmt.lint
.PHONY: lint-go

lint-shell: bin/shellcheck
# skip files that have a non-shell shebang (e.g. Python files)
	@bin/shellcheck -x -e 1071 \
		snap/hooks/* \
		snap/local/tree/bin/* \
		snap/local/tree/sbin/* \
		snap/local/tree/helpers/* \
		utilities/release-*
.PHONY: lint-shell

format.parallel:
	@$(MAKE) -s -j format
.PHONY: format.parallel

# Apply automated formatting to all Python, Sass and Javascript files.
format: format-py format-go
.PHONY: format

format-py: sources = $(wildcard *.py contrib/*.py) $(PY_SOURCES) utilities etc
format-py: bin/black bin/isort
	@bin/isort --recursive $(sources)
	@bin/black -q $(sources)
.PHONY: format-py

format-go:
	@$(MAKE) -C src/machine-resources format
.PHONY: format-go

check: clean test
.PHONY: check

api-docs.rst: bin/maas-region src/maasserver/api/doc_handler.py syncdb
	bin/maas-region generate_api_doc > $@

sampledata: bin/maas-region bin/database syncdb
	$(dbrun) bin/maas-region generate_sample_data
.PHONY: sampledata

doc: api-docs.rst
.PHONY: doc

.run: run-skel
	@cp --archive --verbose $^ $@

.idea: contrib/pycharm
	@cp --archive --verbose $^ $@

pycharm: .idea
.PHONY: pycharm

clean-ui:
	$(MAKE) -C src/maasui clean
.PHONY: clean-ui

clean-ui-build:
	$(MAKE) -C src/maasui clean-build
.PHONY: clean-build

clean-machine-resources:
	$(MAKE) -C src/machine-resources clean
.PHONY: clean-machine-resources

clean: stop clean-failed clean-ui clean-machine-resources
	find . -type f -name '*.py[co]' -print0 | xargs -r0 $(RM)
	find . -type d -name '__pycache__' -print0 | xargs -r0 $(RM) -r
	find . -type f -name '*~' -print0 | xargs -r0 $(RM)
	$(RM) src/maasserver/data/templates.py
	$(RM) *.log
	$(RM) api-docs.rst
	$(RM) .coverage .coverage.* coverage.xml
	$(RM) -r coverage
	$(RM) -r .hypothesis
	$(RM) -r bin include lib local
	$(RM) -r eggs develop-eggs
	$(RM) -r build dist logs/* parts
	$(RM) tags TAGS .installed.cfg
	$(RM) -r *.egg *.egg-info src/*.egg-info
	$(RM) -r services/*/supervise
	$(RM) -r .run
	$(RM) -r .idea
	$(RM) junit.xml
	$(RM) xunit.*.xml
	$(RM) .failed
	$(RM) -r $(VENV)
.PHONY: clean

clean+db: clean
	while fuser db --kill -TERM; do sleep 1; done
	$(RM) -r db
	$(RM) .db.lock
.PHONY: clean+db

harness: bin/maas-region bin/database
	$(dbrun) bin/maas-region shell --settings=maasserver.djangosettings.demo
.PHONY: harness

dbharness: bin/database
	bin/database --preserve shell
.PHONY: dbharness

syncdb: bin/maas-region bin/database
	$(dbrun) bin/maas-region dbupgrade
.PHONY: syncdb

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
.PHONY: run-region
run-rack:
	@services/run $(service_names_rack)
.PHONY: run-rack
run:
	@services/run $(service_names_all)
.PHONY: run

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

services/rackd/@deps: bin/rackd bin/maas-rack bin/maas-common bin/maas-power

services/reloader/@deps:

services/regiond/@deps: bin/maas-region bin/maas-rack bin/maas-common bin/maas-power

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
packaging-version := $(shell utilities/package-version)
tmp_changelog := $(shell tempfile)
packaging-dir := maas_$(packaging-version)
packaging-orig-tar := $(packaging-dir).orig.tar
packaging-orig-targz := $(packaging-dir).orig.tar.gz

machine_resources_vendor := src/machine-resources/vendor

-packaging-clean:
	rm -rf $(packaging-build-area)
	mkdir -p $(packaging-build-area)
.PHONY: -packaging-clean

-packaging-export-orig: $(UI_BUILD) $(OFFLINE_DOCS) $(packaging-build-area)
	git archive --format=tar $(packaging-export-extra) \
            --prefix=$(packaging-dir)/ \
	    -o $(packaging-build-area)/$(packaging-orig-tar) HEAD
	tar -rf $(packaging-build-area)/$(packaging-orig-tar) $(UI_BUILD) $(OFFLINE_DOCS) \
		--transform 's,^,$(packaging-dir)/,'
	$(MAKE) machine-resources-vendor
	tar -rf $(packaging-build-area)/$(packaging-orig-tar) $(machine_resources_vendor) \
		--transform 's,^,$(packaging-dir)/,'
	gzip -f $(packaging-build-area)/$(packaging-orig-tar)
.PHONY: -packaging-export-orig

-packaging-export-orig-uncommitted: $(UI_BUILD) $(OFFLINE_DOCS) $(packaging-build-area)
	git ls-files --others --exclude-standard --cached | grep -v '^debian' | \
	    xargs tar --transform 's,^,$(packaging-dir)/,' -cf $(packaging-build-area)/$(packaging-orig-tar)
	tar -rf $(packaging-build-area)/$(packaging-orig-tar) $(UI_BUILD) $(OFFLINE_DOCS) \
		--transform 's,^,$(packaging-dir)/,'
	$(MAKE) machine-resources-vendor
	tar -rf $(packaging-build-area)/$(packaging-orig-tar) $(machine_resources_vendor) \
		--transform 's,^,$(packaging-dir)/,'
	gzip -f $(packaging-build-area)/$(packaging-orig-tar)
.PHONY: -packaging-export-orig-uncommitted

-packaging-export: -packaging-export-orig$(if $(export-uncommitted),-uncommitted,)
.PHONY: -packaging-export

-package-tree: -packaging-export
	(cd $(packaging-build-area) && tar xfz $(packaging-orig-targz))
	(cp -r debian $(packaging-build-area)/$(packaging-dir))
	echo "maas (1:$(packaging-version)-0ubuntu1) UNRELEASED; urgency=medium" \
	    > $(tmp_changelog)
	tail -n +2 debian/changelog >> $(tmp_changelog)
	mv $(tmp_changelog) $(packaging-build-area)/$(packaging-dir)/debian/changelog
.PHONY: -package-tree

package-tree: -packaging-clean -package-tree

package: package-tree
	(cd $(packaging-build-area)/$(packaging-dir) && debuild -uc -us)
	@echo Binary packages built, see $(packaging-build-area).
.PHONY: package

# To build binary packages from uncommitted changes call "make package-dev".
package-dev:
	$(MAKE) export-uncommitted=yes package
.PHONY: package-dev

source-package: -package-tree
	(cd $(packaging-build-area)/$(packaging-dir) && debuild -S -uc -us)
	@echo Source package built, see $(packaging-build-area).
.PHONY: source-package

# To build source packages from uncommitted changes call "make package-dev".
source-package-dev:
	$(MAKE) export-uncommitted=yes source-package
.PHONY: source-package-dev

# To rebuild packages (i.e. from a clean slate):
package-rebuild: package-clean package
.PHONY: package-rebuild

package-dev-rebuild: package-clean package-dev
.PHONY: package--dev-rebuild

source-package-rebuild: source-package-clean source-package
.PHONY: source-package-rebuild

source-package-dev-rebuild: source-package-clean source-package-dev
.PHONY: source-package-dev-rebuild

# To clean built packages away:
package-clean: patterns := *.deb *.udeb *.dsc *.build *.changes
package-clean: patterns += *.debian.tar.xz *.orig.tar.gz
package-clean:
	@$(RM) -v $(addprefix $(packaging-build-area)/,$(patterns))
.PHONY: package-clean

source-package-clean: patterns := *.dsc *.build *.changes
source-package-clean: patterns += *.debian.tar.xz *.orig.tar.gz
source-package-clean:
	@$(RM) -v $(addprefix $(packaging-build-area)/,$(patterns))
.PHONY: source-package-clean

# Debugging target. Allows printing of any variable.
# As an example, try:
#     make print-scss_input
print-%:
	@echo $* = $($*)

#
# Snap building
#

snap-clean:
# build locally instead of --use-lxd until support for additional repositories
# is enabled by default in snapcraft
	$(snapcraft) clean --destructive-mode
.PHONY: snap-clean

snap:
# build locally instead of --use-lxd until support for additional repositories
# is enabled by default in snapcraft
	$(snapcraft) --destructive-mode
.PHONY: snap

#
# Helpers for using the snap for development testing.
#

DEV_SNAP_DIR ?= build/dev-snap
DEV_SNAP_PRIME_DIR = $(DEV_SNAP_DIR)/prime
DEV_SNAP_PRIME_MARKER = $(DEV_SNAP_PRIME_DIR)/snap/primed

$(DEV_SNAP_DIR): ## Check out a clean version of the working tree.
	git checkout-index -a --prefix $(DEV_SNAP_DIR)/
	git submodule foreach --recursive 'git checkout-index -a --prefix $(PWD)/$(DEV_SNAP_DIR)/$$sm_path/'

$(DEV_SNAP_PRIME_MARKER): $(DEV_SNAP_DIR)
	cd $(DEV_SNAP_DIR) && $(snapcraft) prime --destructive-mode
	touch $@

snap-prime: $(DEV_SNAP_PRIME_MARKER)
.PHONY: snap-prime

sync-dev-snap: RSYNC := rsync -v -r -u -l -t -W -L
sync-dev-snap: $(UI_BUILD) $(DEV_SNAP_PRIME_MARKER)
	$(RSYNC) --exclude 'maastesting' --exclude 'tests' --exclude 'testing' \
		--exclude 'maasui' --exclude 'machine-resources' --exclude 'maas-offline-docs' \
		--exclude '*.pyc' --exclude '__pycache__' \
		src/ $(DEV_SNAP_PRIME_DIR)/lib/python3.8/site-packages/
	$(RSYNC) \
		$(UI_BUILD) $(DEV_SNAP_PRIME_DIR)/usr/share/maas/web/static/
	$(RSYNC) \
		$(OFFLINE_DOCS)/production-html/ $(DEV_SNAP_PRIME_DIR)/usr/share/maas/web/static/docs/
	$(RSYNC) snap/local/tree/ $(DEV_SNAP_PRIME_DIR)/
	$(RSYNC) src/machine-resources/bin/ \
		$(DEV_SNAP_PRIME_DIR)/usr/share/maas/machine-resources/
.PHONY: sync-dev-snap
