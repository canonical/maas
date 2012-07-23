python := python2.7
buildout := bin/buildout
virtualenv := virtualenv

# Python enum modules.
py_enums := $(wildcard src/*/enum.py)
# JavaScript enum module (not modules).
js_enums := src/maasserver/static/js/enums.js

# Prefix commands with this when they need access to the database.
# Remember to add a dependency on bin/database from the targets in
# which those commands appear.
dbrun := bin/database --preserve run --

# For things that care, postgresfixture for example, we always want to
# use the "maas" databases.
export PGDATABASE := maas

build: \
    bin/buildout \
    bin/database \
    bin/maas bin/test.maas bin/test.maastesting \
    bin/twistd.pserv bin/test.pserv \
    bin/twistd.txlongpoll \
    bin/py bin/ipy \
    $(js_enums)

# Note: the following target may not be needed. It remains as an
# experiment, to see if it helps the situation with building MAAS in
# the QA environment, which is isolated from the Internet at large.
build-offline: buildout := $(buildout) buildout:offline=true
build-offline: virtualenv := $(virtualenv) --never-download
build-offline: build

all: build doc

bin/python bin/pip:
	$(virtualenv) --python=$(python) --system-site-packages $(CURDIR)

bin/buildout: bin/pip bootstrap/zc.buildout-1.5.2.tar.gz
	bin/pip --quiet install --ignore-installed \
	    --no-dependencies bootstrap/zc.buildout-1.5.2.tar.gz
	$(RM) -f README.txt  # zc.buildout installs an annoying README.txt.
	@touch --no-create $@  # Ensure it's newer than its dependencies.

bin/database: bin/buildout buildout.cfg versions.cfg setup.py
	$(buildout) install database
	@touch --no-create $@

bin/maas: bin/buildout buildout.cfg versions.cfg setup.py $(js_enums)
	$(buildout) install maas
	@touch --no-create $@

bin/test.maas: bin/buildout buildout.cfg versions.cfg setup.py $(js_enums)
	$(buildout) install maas-test
	@touch --no-create $@

bin/test.maastesting: bin/buildout buildout.cfg versions.cfg setup.py
	$(buildout) install maastesting-test
	@touch --no-create $@

bin/twistd.pserv: bin/buildout buildout.cfg versions.cfg setup.py
	$(buildout) install pserv
	@touch --no-create $@

bin/test.pserv: bin/buildout buildout.cfg versions.cfg setup.py
	$(buildout) install pserv-test
	@touch --no-create $@

bin/twistd.txlongpoll: bin/buildout buildout.cfg versions.cfg setup.py
	$(buildout) install txlongpoll
	@touch --no-create $@

bin/flake8: bin/buildout buildout.cfg versions.cfg setup.py
	$(buildout) install flake8
	@touch --no-create $@

bin/sphinx: bin/buildout buildout.cfg versions.cfg setup.py
	$(buildout) install sphinx
	@touch --no-create $@

bin/py bin/ipy: bin/buildout buildout.cfg versions.cfg setup.py
	$(buildout) install repl
	@touch --no-create bin/py bin/ipy

test: build
	echo $(wildcard bin/test.*) | xargs -n1 env

lint: sources = $(wildcard *.py contrib/*.py) src templates twisted utilities
lint: bin/flake8
	@find $(sources) -name '*.py' ! -path '*/migrations/*' \
	    -print0 | xargs -r0 bin/flake8

pocketlint = $(call available,pocketlint,python-pocket-lint)

lint-css: sources = src/maasserver/static/css
lint-css:
	@find $(sources) -type f \
	    -print0 | xargs -r0 $(pocketlint) --max-length=120

lint-js: sources = src/maasserver/static/js
lint-js:
	@find $(sources) -type f -print0 | xargs -r0 $(pocketlint)

check: clean test

docs/api.rst: bin/maas src/maasserver/api.py syncdb
	bin/maas generate_api_doc > $@

sampledata: bin/maas bin/database syncdb
	$(dbrun) bin/maas loaddata src/maasserver/fixtures/dev_fixture.yaml

doc: bin/sphinx docs/api.rst
	bin/sphinx

enums: $(js_enums)

$(js_enums): bin/py src/maasserver/utils/jsenums.py $(py_enums)
	 bin/py -m src/maasserver/utils/jsenums $(py_enums) > $@

clean:
	find . -type f -name '*.py[co]' -print0 | xargs -r0 $(RM)
	find . -type f -name '*~' -print0 | xargs -r0 $(RM)
	$(RM) -r media/demo/* media/development
	$(RM) $(js_enums)
	$(RM) *.log
	$(RM) celerybeat-schedule
	$(RM) docs/api.rst
	$(RM) -r docs/_autosummary

distclean: clean stop
	$(RM) -r bin include lib local
	$(RM) -r eggs develop-eggs
	$(RM) -r build dist logs/* parts
	$(RM) tags TAGS .installed.cfg
	$(RM) -r *.egg *.egg-info src/*.egg-info
	$(RM) -r docs/_build
	$(RM) -r run/* services/*/supervise
	$(RM) twisted/plugins/dropin.cache

harness: bin/maas bin/database
	$(dbrun) bin/maas shell --settings=maas.demo

dbharness: bin/database
	bin/database --preserve shell

syncdb: bin/maas bin/database
	$(dbrun) bin/maas syncdb --noinput
	$(dbrun) bin/maas migrate maasserver --noinput
	$(dbrun) bin/maas migrate metadataserver --noinput

define phony_targets
  build
  build-offline
  check
  clean
  dbharness
  distclean
  doc
  enums
  harness
  lint
  lint-css
  lint-js
  sampledata
  syncdb
  test
endef

#
# Development services.
#

service_names := celeryd database dns pserv reloader txlongpoll web webapp
services := $(patsubst %,services/%/,$(service_names))

run:
	@services/run $(service_names)

run+webapp:
	@services/run $(service_names) +webapp

start: $(addsuffix @start,$(services))

pause: $(addsuffix @pause,$(services))

status: $(addsuffix @status,$(services))

restart: $(addsuffix @restart,$(services))

stop: $(addsuffix @stop,$(services))

supervise: $(addsuffix @supervise,$(services))

define phony_services_targets
  pause
  restart
  run
  run+webapp
  start
  status
  stop
  supervise
endef

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

services/celeryd/@deps:

services/database/@deps: bin/database

services/pserv/@deps: bin/twistd.pserv

services/reloader/@deps:

services/txlongpoll/@deps: bin/twistd.txlongpoll

services/web/@deps:

services/webapp/@deps: bin/maas

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
