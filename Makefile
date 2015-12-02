python := python2.7

# pkg_resources makes some incredible noise about version numbers. They
# are not indications of bugs in MAAS so we silence them everywhere.
export PYTHONWARNINGS = \
  ignore:You have iterated over the result:RuntimeWarning:pkg_resources:

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
    $(wildcard src/maasserver/static/scss/*/*.scss) \
    $(wildcard src/maasserver/static/scss/*/*/*.scss)
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
    bin/test.e2e \
    bin/test.js \
    bin/test.region \
    bin/test.testing \
    bin/py bin/ipy \
    $(js_enums)

all: build doc

release_codename = $(shell lsb_release -c -s)

# Install all packages required for MAAS development & operation on
# the system. This may prompt for a password.
install-dependencies:
	sudo DEBIAN_FRONTEND=noninteractive apt-get -y \
	    --no-install-recommends install $(shell sort -u \
	        $(addprefix required-packages/,base build dev doc $(release_codename)))
	sudo DEBIAN_FRONTEND=noninteractive apt-get -y \
	    purge $(shell sort -u required-packages/forbidden)

.gitignore: .bzrignore
	sed 's:^[.]/:/:' $^ > $@
	echo '/src/**/*.pyc' >> $@
	echo '/etc/**/*.pyc' >> $@

bin/python:
	$(virtualenv) --python=$(python) --system-site-packages $(CURDIR)

configure-buildout:
	utilities/configure-buildout

bin/buildout: bin/python bootstrap/zc.buildout-1.5.2.tar.gz
	@utilities/configure-buildout --quiet
	bin/python -m pip --quiet install --ignore-installed \
	    --no-dependencies bootstrap/zc.buildout-1.5.2.tar.gz
	$(RM) README.txt  # zc.buildout installs an annoying README.txt.
	@touch --no-create $@  # Ensure it's newer than its dependencies.

bin/database: bin/buildout buildout.cfg versions.cfg setup.py
	$(buildout) install database
	@touch --no-create $@

bin/maas-region-admin bin/twistd.region: \
    bin/buildout buildout.cfg versions.cfg setup.py $(js_enums)
	$(buildout) install region
	@touch --no-create $@

bin/test.region: \
    bin/buildout buildout.cfg versions.cfg setup.py $(js_enums)
	$(buildout) install region-test
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

bin/test.e2e: bin/protractor bin/buildout buildout.cfg versions.cfg setup.py
	$(buildout) install e2e-test
	@touch --no-create $@

bin/test.testing: \
	bin/buildout bin/sass buildout.cfg versions.cfg setup.py
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

bin/rst-lint: bin/buildout buildout.cfg versions.cfg setup.py
	$(buildout) install rst-lint
	@touch --no-create $@

bin/sphinx bin/sphinx-build: bin/buildout buildout.cfg versions.cfg setup.py
	$(buildout) install sphinx
	@touch --no-create $@

bin/py bin/ipy: bin/buildout buildout.cfg versions.cfg setup.py
	$(buildout) install repl
	@touch --no-create bin/py bin/ipy

define karma-deps
  karma@0.12.32
  karma-chrome-launcher@0.1.12
  karma-firefox-launcher@0.1.6
  karma-jasmine@0.3.5
  karma-opera-launcher@0.1.0
  karma-phantomjs-launcher@0.1.4
  karma-failed-reporter@0.0.3
endef

bin/karma: deps = $(strip $(karma-deps))
bin/karma: prefix = include/nodejs
bin/karma:
	@mkdir -p $(@D) $(prefix)
	npm install --cache-min 600 --prefix $(prefix) $(deps)
	@ln -srf $(prefix)/node_modules/karma/bin/karma $@

bin/protractor: prefix = include/nodejs
bin/protractor:
	@mkdir -p $(@D) $(prefix)
	npm install --cache-min 600 --prefix $(prefix) protractor@2.0.0
	@ln -srf $(prefix)/node_modules/protractor/bin/protractor $@

bin/sass: prefix = include/nodejs
bin/sass:
	@mkdir -p $(@D) $(prefix)
	npm install --cache-min 600 --prefix $(prefix) node-sass@3.1.0
	@ln -srf $(prefix)/node_modules/node-sass/bin/node-sass $@

test: test-scripts-all = $(wildcard bin/test.*)
# Don't run bin/test.e2e for now; it breaks.
test: test-scripts = $(filter-out bin/test.e2e,$(test-scripts-all))
test: build
	@$(RM) coverage.data
	@echo $(test-scripts) | xargs --verbose -n1 env

test+coverage: export NOSE_WITH_COVERAGE = 1
test+coverage: test

coverage-report: coverage/index.html
	sensible-browser $< > /dev/null 2>&1 &

coverage.xml: coverage.data
	python-coverage xml --include 'src/*' -o $@

coverage/index.html: coverage.data
	@$(RM) -r $(@D)
	python-coverage html --include 'src/*' -d $(@D)

coverage.data:
	@$(error Use `$(MAKE) test` to generate coverage data, or invoke a \
            test script using the `--with-coverage` flag)

lint: lint-py lint-js lint-doc lint-rst

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
	    | xargs -r0 -n50 -P4 bin/flake8 --ignore=E123,E402,E731 \
	    --config=/dev/null
	@utilities/check-maaslog-exception

lint-doc:
	@utilities/doc-lint

# lint-rst 0.11.1 shouldn't be used on our documentation because it
# doesn't understand Sphinx's extensions, and doesn't grok linking
# between documents, hence complaints about broken links. However,
# Sphinx itself warns about lint when building the docs.
lint-rst: sources = README HACKING.txt schema/README.rst
lint-rst: bin/rst-lint
	@find $(sources) -type f \
	    -printf 'Linting %p...\n' \
	    -exec bin/rst-lint --encoding=utf8 {} \;

# JavaScript lint is checked in parallel for speed.  The -n20 -P4 setting
# worked well on a multicore SSD machine with the files cached, roughly
# doubling the speed, but it may need tuning for slower systems or cold caches.
lint-js: sources = src/maasserver/static/js
lint-js:
	@find $(sources) -type f ! -path '*/angular/3rdparty/*' -print0 '(' -name '*.html' -o -name '*.js' ')' \
		| xargs -r0 -n20 -P4 $(pocketlint)

# Apply automated formatting to all Python files.
format: sources = $(wildcard *.py contrib/*.py) src templates twisted utilities etc
format:
	@find $(sources) -name '*.py' -print0 | xargs -r0 utilities/format-imports

# Update copyright dates from version history. Try to avoid updating
# 3rd-party code by checking for "Canonical" or "MAAS" on the same line
# as the copyright header.
copyright:
	@bzr ls --versioned --recursive --kind=file --null | \
	    xargs -r0 egrep -iI 'copyright.*(canonical|maas)' -lZ | \
	    xargs -r0 bzr update-copyright --quiet --force-range

check: clean test

docs/api.rst: bin/maas-region-admin src/maasserver/api/doc_handler.py syncdb
	bin/maas-region-admin generate_api_doc > $@

sampledata: bin/maas-region-admin bin/database syncdb
	$(dbrun) bin/maas-region-admin loaddata src/maasserver/fixtures/dev_fixture.yaml

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

enums: $(js_enums)

$(js_enums): bin/py src/maasserver/utils/jsenums.py $(py_enums)
	 bin/py -m maasserver/utils/jsenums $(py_enums) > $@

styles: bin/sass clean-styles $(scss_output)

$(scss_output): $(scss_inputs)
	bin/sass --include-path=src/maasserver/static/scss --output-style compressed $< -o $(dir $@)

clean-styles:
	$(RM) $(scss_output)

clean: stop clean-run
	$(MAKE) -C acceptance $@
	find . -type f -name '*.py[co]' -print0 | xargs -r0 $(RM)
	find . -type f -name '*~' -print0 | xargs -r0 $(RM)
	find . -type f -name dropin.cache -print0 | xargs -r0 $(RM)
	$(RM) -r media/demo/* media/development
	$(RM) $(js_enums)
	$(RM) *.log
	$(RM) docs/api.rst
	$(RM) -r docs/_autosummary docs/_build
	$(RM) -r man/.doctrees
	$(RM) coverage.data coverage.xml
	$(RM) -r coverage
	$(RM) -r .hypothesis
	$(RM) -r bin include lib local
	$(RM) -r eggs develop-eggs
	$(RM) -r build dist logs/* parts
	$(RM) tags TAGS .installed.cfg
	$(RM) -r *.egg *.egg-info src/*.egg-info
	$(RM) -r services/*/supervise

# Be selective about what to remove from run and run-e2e.
define clean-run-template
find $(1) -depth ! -type d \
    ! -path $(1)/etc/maas/templates \
    ! -path $(1)/etc/maas/drivers.yaml \
    -print0 | xargs -r0 $(RM)
find $(1) -depth -type d \
    -print0 | xargs -r0 rmdir --ignore-fail-on-non-empty
endef

clean-run:
	$(call clean-run-template,run)
	$(call clean-run-template,run-e2e)

clean+db: clean
	$(RM) -r db
	$(RM) .db.lock

distclean: clean
	$(warning 'distclean' is deprecated; use 'clean')

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
	$(dbrun) pg_dump -h $(CURDIR)/db -d maas --no-owner --no-privileges -f $@

# Synchronise the database, and update the baseline schema.
baseline-schema: syncdb schema/baseline.sql

define phony_targets
  build
  check
  clean
  clean+db
  clean-run
  clean-styles
  configure-buildout
  copyright
  coverage-report
  dbharness
  distclean
  doc
  doc-browse
  enums
  format
  harness
  install-dependencies
  lint
  lint-css
  lint-doc
  lint-js
  lint-py
  lint-rst
  man
  sampledata
  styles
  syncdb
  test
  test+coverage
endef

#
# Development services.
#

service_names_region := database dns regiond regiond2 reloader
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

services/regiond/@deps: bin/maas-region-admin

services/regiond2/@deps: bin/maas-region-admin

#
# Package building
#

# This ought to be as simple as using bzr builddeb --export-upstream but it
# has a bug and always considers apt-source tarballs before the specified
# branch. Instead, export to a local tarball which is always found. Make sure
# the packages listed in `required-packages/build` are installed before using
# this.

# Old names.
PACKAGING := $(abspath ../packaging-1.9)
PACKAGING_BRANCH := lp:~maas-maintainers/maas/packaging-1.9

packaging-tree = $(PACKAGING)
packaging-branch = $(PACKAGING_BRANCH)

packaging-build-area := $(abspath ../build-area)
packaging-version = $(shell \
   dpkg-parsechangelog -l$(packaging-tree)/debian/changelog \
       | sed -rne 's,^Version: ([^-]+).*,\1,p')

$(packaging-build-area):
	mkdir -p $(packaging-build-area)

-packaging-fetch:
	bzr branch $(packaging-branch) $(packaging-tree)

-packaging-pull:
	bzr pull -d $(packaging-tree)

-packaging-refresh: -packaging-$(shell \
    test -d $(packaging-tree) && echo "pull" || echo "fetch")

-packaging-export-orig: $(packaging-build-area)
	bzr export $(packaging-export-extra) --root=maas-$(packaging-version).orig \
	    $(packaging-build-area)/maas_$(packaging-version).orig.tar.gz

# To build binary packages from uncommitted changes:
#     make package-export-extra=--uncommitted package
package: -packaging-refresh -packaging-export-orig
	bzr bd --merge $(packaging-tree) --result-dir=$(packaging-build-area) -- -uc -us
	@echo Binary packages built, see $(packaging-build-area).

# ... or use the `package-dev` target.
package-dev: packaging-export-extra = --uncommitted
package-dev: package

# To build a source package from uncommitted changes:
#     make package-export-extra=--uncommitted source-package
source-package: -packaging-refresh -packaging-export-orig
	bzr bd --merge $(packaging-tree) --result-dir=$(packaging-build-area) -- -S -uc -us
	@echo Source package built, see $(packaging-build-area).

# ... or use the `source-package-dev` target.
source-package-dev: packaging-export-extra = --uncommitted
source-package-dev: source-package

# To rebuild packages (i.e. from a clean slate):
package-rebuild: package-clean package

package-dev-rebuild: package-clean package-dev

source-package-rebuild: source-package-clean source-package

source-package-dev-rebuild: source-package-clean source-package-dev

# To clean built packages away:
package-clean: patterns := *.deb *.dsc *.build *.changes
package-clean: patterns += *.debian.tar.xz *.orig.tar.gz
package-clean:
	@$(RM) -v $(addprefix $(packaging-build-area)/,$(patterns))

source-package-clean: patterns := *.dsc *.build *.changes
source-package-clean: patterns += *.debian.tar.xz *.orig.tar.gz
source-package-clean:
	@$(RM) -v $(addprefix $(packaging-build-area)/,$(patterns))

define phony_package_targets
  -packaging-export-orig
  -packaging-fetch
  -packaging-pull
  -packaging-refresh
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
# Phony stuff.
#

define phony
  $(phony_package_targets)
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
