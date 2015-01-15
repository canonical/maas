python := python2.7

# Network activity can be suppressed by setting offline=true (or any
# non-empty string) at the command-line.
ifeq ($(offline),)
buildout := bin/buildout
virtualenv := virtualenv
else
buildout := bin/buildout buildout:offline=true
virtualenv := virtualenv --never-download
endif

# If offline has been selected, attempt to further block HTTP/HTTPS
# activity by setting bogus proxies in the environment.
ifneq ($(offline),)
export http_proxy := broken
export https_proxy := broken
endif

# Python enum modules.
py_enums := $(wildcard src/*/enum.py)
# JavaScript enum module (not modules).
js_enums := src/maasserver/static/js/enums.js

# MAAS SASS stylesheets. The first input file (maas-styles.css) imports
# the others, so is treated specially in the target definitions.
scss_inputs := \
    src/maasserver/static/scss/maas-styles.scss \
    $(wildcard src/maasserver/static/scss/**/*.scss)
scss_output := src/maasserver/static/css/maas-styles.css

# Prefix commands with this when they need access to the database.
# Remember to add a dependency on bin/database from the targets in
# which those commands appear.
dbrun := bin/database --preserve run --

# For things that care, postgresfixture for example, we always want to
# use the "maas" databases.
export PGDATABASE := maas

# For anything we start, we want to hint as to its root directory.
export MAAS_ROOT := $(CURDIR)/run

build: \
    bin/buildout \
    bin/database \
    bin/maas \
    bin/maas-probe-dhcp \
    bin/maas-provision \
    bin/maas-region-admin \
    bin/twistd.cluster \
    bin/twistd.region \
    bin/test.cli \
    bin/test.cluster \
    bin/test.config \
    bin/test.region \
    bin/test.testing \
    bin/py bin/ipy \
    $(js_enums) \
    $(scss_output)

all: build doc

# Install all packages required for MAAS development & operation on
# the system. This may prompt for a password.
install-dependencies:
	sudo DEBIAN_FRONTEND=noninteractive apt-get -y \
	    --no-install-recommends install $(shell sort -u \
	        $(addprefix required-packages/,base build dev doc))
	sudo DEBIAN_FRONTEND=noninteractive apt-get -y \
	    purge $(shell sort -u required-packages/forbidden)

bin/python:
	$(virtualenv) --python=$(python) --system-site-packages $(CURDIR)

bin/buildout: bin/python bootstrap/zc.buildout-1.5.2.tar.gz
	bin/python -m pip --quiet install --ignore-installed \
	    --no-dependencies bootstrap/zc.buildout-1.5.2.tar.gz
	$(RM) -f README.txt  # zc.buildout installs an annoying README.txt.
	@touch --no-create $@  # Ensure it's newer than its dependencies.

bin/database: bin/buildout buildout.cfg versions.cfg setup.py
	$(buildout) install database
	@touch --no-create $@

bin/maas-region-admin bin/twistd.region: \
    bin/buildout buildout.cfg versions.cfg setup.py $(js_enums) $(scss_output)
	$(buildout) install region
	@touch --no-create $@

bin/test.region: \
    bin/buildout buildout.cfg versions.cfg setup.py $(js_enums) $(scss_output)
	$(buildout) install region-test
	@touch --no-create $@

bin/maas: bin/buildout buildout.cfg versions.cfg setup.py
	$(buildout) install cli
	@touch --no-create $@

bin/test.cli: bin/buildout buildout.cfg versions.cfg setup.py
	$(buildout) install cli-test
	@touch --no-create $@

bin/test.testing: bin/buildout buildout.cfg versions.cfg setup.py
	$(buildout) install testing-test
	@touch --no-create $@

bin/maas-probe-dhcp bin/maas-provision bin/twistd.cluster: \
    bin/buildout buildout.cfg versions.cfg setup.py
	$(buildout) install cluster
	@touch --no-create $@

bin/test.cluster: bin/buildout buildout.cfg versions.cfg setup.py
	$(buildout) install cluster-test
	@touch --no-create $@

bin/test.config: bin/buildout buildout.cfg versions.cfg setup.py
	$(buildout) install config-test
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

test: build
	echo $(wildcard bin/test.*) | xargs -n1 env

lint: lint-py lint-js lint-doc

pocketlint = $(call available,pocketlint,python-pocket-lint)

# XXX jtv 2014-02-25: Clean up this lint, then make it part of "make lint".
lint-css: sources = src/maasserver/static/css
lint-css:
	@find $(sources) -type f \
	    -print0 | xargs -r0 $(pocketlint) --max-length=120

# Python lint checks are time-intensive, so we run them in parallel.  It may
# make things matters worse if the files need to be read from disk, though, so
# this may need more tuning.
# The -n50 -P4 setting roughly doubled speed on a high-end system with SSD and
# all the files in cache.
lint-py: sources = $(wildcard *.py contrib/*.py) src templates twisted utilities etc
lint-py: bin/flake8
	@find $(sources) -name '*.py' ! -path '*/migrations/*' -print0 \
	    | xargs -r0 -n50 -P4 bin/flake8 --ignore=E123 --config=/dev/null
	@./utilities/check-maaslog-exception

lint-doc:
	@./utilities/doc-lint

# JavaScript lint is checked in parallel for speed.  The -n20 -P4 seetting
# worked well on a multicore SSD machine with the files cached, roughly
# doubling the speed, but it may need tuning for slower systems or cold caches.
lint-js: sources = src/maasserver/static/js
lint-js:
	@find $(sources) -type f -print0 '(' -name '*.html' -o -name '*.js' ')' | xargs -r0 -n20 -P4 $(pocketlint)

# Apply automated formatting to all Python files.
format: sources = $(wildcard *.py contrib/*.py) src templates twisted utilities etc
format:
	@find $(sources) -name '*.py' -print0 | xargs -r0 ./utilities/format-imports

check: clean test

docs/api.rst: bin/maas-region-admin src/maasserver/api/doc_handler.py syncdb
	bin/maas-region-admin generate_api_doc > $@

sampledata: bin/maas-region-admin bin/database syncdb
	$(dbrun) bin/maas-region-admin loaddata src/maasserver/fixtures/dev_fixture.yaml

doc: bin/sphinx docs/api.rst
	bin/sphinx

doc-with-versions: bin/sphinx docs/api.rst
	cd docs/_build; make SPHINXOPTS="-A add_version_switcher=true" html

man: $(patsubst docs/man/%.rst,man/%,$(wildcard docs/man/*.rst))

man/%: docs/man/%.rst | bin/sphinx-build
	bin/sphinx-build -b man docs man $^

enums: $(js_enums)

$(js_enums): bin/py src/maasserver/utils/jsenums.py $(py_enums)
	 bin/py -m src/maasserver/utils/jsenums $(py_enums) > $@

styles: $(scss_output)

$(scss_output): $(scss_inputs)
	pyscss $< -o $@ --load-path=src/maasserver/static/scss

clean:
	$(MAKE) -C acceptance $@
	find . -type f -name '*.py[co]' -print0 | xargs -r0 $(RM)
	find . -type f -name '*~' -print0 | xargs -r0 $(RM)
	find . -type f -name dropin.cache -print0 | xargs -r0 $(RM)
	$(RM) -r media/demo/* media/development
	$(RM) $(js_enums)
	$(RM) $(scss_output)
	$(RM) *.log
	$(RM) docs/api.rst
	$(RM) -r docs/_autosummary docs/_build
	$(RM) -r man/.doctrees

distclean: clean stop
	$(RM) -r bin include lib local
	$(RM) -r eggs develop-eggs
	$(RM) -r build dist logs/* parts
	$(RM) tags TAGS .installed.cfg
	$(RM) -r *.egg *.egg-info src/*.egg-info
	$(RM) -r run/* services/*/supervise

harness: bin/maas-region-admin bin/database
	$(dbrun) bin/maas-region-admin shell --settings=maas.demo

dbharness: bin/database
	bin/database --preserve shell

syncdb: bin/maas-region-admin bin/database
	$(dbrun) bin/maas-region-admin syncdb --noinput
	$(dbrun) bin/maas-region-admin migrate maasserver --noinput
	$(dbrun) bin/maas-region-admin migrate metadataserver --noinput

# (Re)write the baseline schema.
schema/baseline.sql: bin/database
	$(dbrun) pg_dump -h $(PWD)/db/ -d maas --no-owner --no-privileges -f $@

# Synchronise the database, and update the baseline schema.
baseline-schema: syncdb schema/baseline.sql

define phony_targets
  build
  check
  clean
  dbharness
  distclean
  doc
  enums
  format
  harness
  install-dependencies
  lint
  lint-css
  lint-doc
  lint-js
  lint-py
  man
  package
  sampledata
  source_package
  styles
  syncdb
  test
endef

#
# Development services.
#

service_names_region := database dns regiond regiond2 reloader web
service_names_cluster := clusterd reloader
service_names_all := $(service_names_region) $(service_names_cluster)

# The following template is intended to be used with `call`, and it
# accepts a single argument: a target name. The target name must
# correspond to a service action (see "Pseudo-magic targets" below).
# A region- and cluster-specific variant of the target will be
# created, in addition to the target itself. These can be used to
# apply the service action to the region services, the cluster
# services, or all services, at the same time.
define service_template
$(1)-region: $(patsubst %,services/%/@$(1),$(service_names_region))
$(1)-cluster: $(patsubst %,services/%/@$(1),$(service_names_cluster))
$(1): $(1)-region $(1)-cluster
phony_services_targets += $(1)-region $(1)-cluster $(1)
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
run-cluster:
	@services/run $(service_names_cluster)
run:
	@services/run $(service_names_all)

phony_services_targets += run-region run-cluster run

# This one's for the rapper, yo. Don't run the load-balancing regiond2.
run+regiond:
	@services/run $(filter-out regiond2,$(service_names_region)) +regiond

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

services/dns/@deps: bin/py

services/database/@deps: bin/database

services/clusterd/@deps: bin/twistd.cluster

services/reloader/@deps:

services/web/@deps:

services/regiond/@deps: bin/maas-region-admin

services/regiond2/@deps: bin/maas-region-admin

#
# Package building
#
# This ought to be as simple as using bzr builddeb --export-upstream but it
# has a bug and always considers apt-source tarballs before the specified
# branch.  So instead, export to a local tarball which is always found.
# Make sure debhelper and dh-apport packages are installed before using this.
PACKAGING := $(CURDIR)/../packaging.trunk
PACKAGING_BRANCH := lp:~maas-maintainers/maas/packaging

package_branch:
	@echo Downloading/refreshing packaging branch...
	@if [ ! -d $(PACKAGING) ]; then \
		bzr branch $(PACKAGING_BRANCH) $(PACKAGING); \
		else bzr pull -d $(PACKAGING); fi

# Make sure an orig tarball generated from the current branch is placed in the
# build area.
package_export: VER = $(shell dpkg-parsechangelog -l$(PACKAGING)/debian/changelog | sed -rne 's,^Version: ([^-]+).*,\1,p')
package_export: TARBALL = maas_$(VER).orig.tar.gz
package_export: package_branch
	@$(RM) -f ../build-area/$(TARBALL)
	@mkdir -p ../build-area
	@bzr export --root=maas-$(VER).orig ../build-area/$(TARBALL) $(CURDIR)

package: package_export
	bzr bd --merge $(PACKAGING) --result-dir=../build-area -- -uc -us
	@echo Binary packages built, see ../build-area/ directory.

source_package: package_export
	bzr bd --merge $(PACKAGING) --result-dir=../build-area -- -S -uc -us
	@echo Source package built, see ../build-area/ directory.

#
# Phony stuff.
#

define phony
  $(phony_services_targets)
  $(phony_targets)
endef

phony := $(sort $(strip $(phony)))

.PHONY: $(phony)

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
