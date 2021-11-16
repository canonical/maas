python := python3
snapcraft := SNAPCRAFT_BUILD_INFO=1 /snap/bin/snapcraft

VENV := .ve

# PPA used by MAAS dependencies. It can be overridden by the env.
#
# This uses an explicit empty check (rather than ?=) since Jenkins defines
# variables for parameters even when not passed.
ifeq ($(MAAS_PPA),)
	MAAS_PPA = ppa:maas-committers/latest-deps
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

# Default PostgreSQL tools to use the maas database
export PGDATABASE := maas

.DEFAULT_GOAL := build

define BIN_SCRIPTS
bin/maas \
bin/maas-common \
bin/maas-power \
bin/maas-rack \
bin/maas-region \
bin/postgresfixture \
bin/pytest \
bin/rackd \
bin/regiond \
bin/subunit-1to2 \
bin/subunit2junitxml \
bin/subunit2pyunit \
bin/test.parallel \
bin/test.rack \
bin/test.region \
bin/test.region.legacy
endef

UI_BUILD := src/maasui/build

OFFLINE_DOCS := src/maas-offline-docs/src

build: \
  .run \
  $(VENV) \
  $(BIN_SCRIPTS) \
  bin/shellcheck \
  bin/py
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
	$(apt_install) software-properties-common
	if [ -n "$(MAAS_PPA)" ]; then sudo apt-add-repository -y $(MAAS_PPA); fi
	$(apt_install) $(foreach deps,$(REQUIRED_DEPS_FILES),$(call list_required,$(deps)))
	sudo DEBIAN_FRONTEND=noninteractive apt purge -y \
		$(foreach deps,$(FORBIDDEN_DEPS_FILES),$(call list_required,$(deps)))
	if [ -x /usr/bin/snap ]; then cat required-packages/snaps | xargs -L1 sudo snap install; fi
.PHONY: install-dependencies

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

test: test-missing-migrations test-py
.PHONY: test

test-missing-migrations: bin/database bin/maas-region
	$(dbrun) bin/maas-region makemigrations --check --dry-run
.PHONY: test-missing-migrations

test-py: bin/test.parallel bin/subunit-1to2 bin/subunit2junitxml bin/subunit2pyunit bin/pytest
	@utilities/run-py-tests-ci
.PHONY: test-py

src/maasserver/testing/initial.maas_test.sql: bin/maas-region bin/database
    # Run migrations without any triggers created.
	$(dbrun) bin/maas-region dbupgrade --internal-no-triggers
    # Data migration will create a notification, that will break tests. Want
    # the database to be a clean schema.
	$(dbrun) bin/maas-region shell -c "from maasserver.models.notification import Notification; Notification.objects.all().delete()"
	$(dbrun) pg_dump maas --no-owner --no-privileges --format=plain > $@

lint: lint-py lint-py-imports lint-py-linefeeds lint-go lint-shell
.PHONY: lint

lint-py:
	@tox -e lint
.PHONY: lint-py

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
		src/metadataserver/builtin_scripts/commissioning_scripts/maas-get-fruid-api-data \
		src/metadataserver/builtin_scripts/commissioning_scripts/maas-kernel-cmdline \
		src/provisioningserver/refresh/40-maas-01-machine-resources \
		src/provisioningserver/refresh/maas-list-modaliases \
		src/provisioningserver/refresh/maas-lshw \
		src/provisioningserver/refresh/maas-serial-ports \
		src/provisioningserver/refresh/maas-support-info \
		utilities/build_custom_ubuntu_image \
		utilities/build_custom_ubuntu_image_no_kernel \
		utilities/connect-snap-interfaces \
		utilities/gen-db-schema-svg \
		utilities/ldap-setup \
		utilities/package-version \
		utilities/run-performanced \
		utilities/run-py-tests-ci
.PHONY: lint-shell

format.parallel:
	@$(MAKE) -s -j format
.PHONY: format.parallel

# Apply automated formatting to all Python, Sass and Javascript files.
format: format-py format-go
.PHONY: format

format-py:
	@tox -e format
.PHONY: format-py

format-go:
	@$(MAKE) -C src/machine-resources format
.PHONY: format-go

check: clean test
.PHONY: check

api-docs.rst: bin/maas-region src/maasserver/api/doc_handler.py syncdb
	bin/maas-region generate_api_doc > $@

sampledata: bin/maas-region bin/database syncdb machine-resources
	$(dbrun) bin/maas-region generate_sample_data
.PHONY: sampledata

doc: api-docs.rst
.PHONY: doc

.run: run-skel
	@cp --archive --verbose $^ $@

clean-ui:
	$(MAKE) -C src/maasui clean
.PHONY: clean-ui

clean-ui-build:
	$(MAKE) -C src/maasui clean-build
.PHONY: clean-build

clean-machine-resources:
	$(MAKE) -C src/machine-resources clean
.PHONY: clean-machine-resources

clean: clean-ui clean-machine-resources
	find . -type f -name '*.py[co]' -print0 | xargs -r0 $(RM)
	find . -type d -name '__pycache__' -print0 | xargs -r0 $(RM) -r
	find . -type f -name '*~' -print0 | xargs -r0 $(RM)
	$(RM) src/maasserver/data/templates.py
	$(RM) *.log
	$(RM) api-docs.rst
	$(RM) -r .hypothesis
	$(RM) -r bin include lib local
	$(RM) -r eggs develop-eggs
	$(RM) -r build dist logs/* parts
	$(RM) tags TAGS .installed.cfg
	$(RM) -r *.egg *.egg-info src/*.egg-info
	$(RM) -r .run
	$(RM) junit*.xml
	$(RM) xunit.*.xml
	$(RM) .noseids
	$(RM) .failed
	$(RM) -r $(VENV)
	$(RM) -r .tox
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
#     make print-BIN_SCRIPTS
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

DEV_SNAP_DIR ?= $(PWD)/build/dev-snap
DEV_SNAP_PRIME_DIR = $(DEV_SNAP_DIR)/prime
DEV_SNAP_PRIME_MARKER = $(DEV_SNAP_PRIME_DIR)/snap/primed

$(DEV_SNAP_DIR): ## Check out a clean version of the working tree.
	git checkout-index -a --prefix $(DEV_SNAP_DIR)/
	git submodule foreach --recursive 'git checkout-index -a --prefix $(DEV_SNAP_DIR)/$$sm_path/'

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
		$(UI_BUILD)/ $(DEV_SNAP_PRIME_DIR)/usr/share/maas/web/static/
	$(RSYNC) \
		$(OFFLINE_DOCS)/production-html-snap/ $(DEV_SNAP_PRIME_DIR)/usr/share/maas/web/static/docs/
	$(RSYNC) snap/local/tree/ $(DEV_SNAP_PRIME_DIR)/
	$(RSYNC) src/machine-resources/bin/ \
		$(DEV_SNAP_PRIME_DIR)/usr/share/maas/machine-resources/
.PHONY: sync-dev-snap
