PYTHON = python2.7

build: \
    bin/buildout \
    bin/maas bin/test.maas \
    bin/twistd.pserv bin/test.pserv \
    bin/twistd.txlongpoll \
    bin/py bin/ipy

all: build doc

bin/buildout: bootstrap.py distribute_setup.py
	$(PYTHON) bootstrap.py --distribute --setup-source distribute_setup.py
	@touch --no-create $@  # Ensure it's newer than its dependencies.

bin/maas: bin/buildout buildout.cfg setup.py
	bin/buildout install maas
	@touch --no-create $@

bin/test.maas: bin/buildout buildout.cfg setup.py
	bin/buildout install maas-test
	@touch --no-create $@

bin/twistd.pserv: bin/buildout buildout.cfg setup.py
	bin/buildout install pserv
	@touch --no-create $@

bin/test.pserv: bin/buildout buildout.cfg setup.py
	bin/buildout install pserv-test
	@touch --no-create $@

bin/twistd.txlongpoll: bin/buildout buildout.cfg setup.py
	bin/buildout install txlongpoll
	@touch --no-create $@

bin/flake8: bin/buildout buildout.cfg setup.py
	bin/buildout install flake8
	@touch --no-create $@

bin/sphinx: bin/buildout buildout.cfg setup.py
	bin/buildout install sphinx
	@touch --no-create $@

bin/py bin/ipy: bin/buildout buildout.cfg setup.py
	bin/buildout install repl
	@touch --no-create bin/py bin/ipy

dev-db:
	utilities/maasdb start ./db/ disposable

test: bin/test.maas bin/test.pserv
	bin/test.maas
	bin/test.pserv

lint: sources = contrib setup.py src templates twisted utilities
lint: bin/flake8
	@find $(sources) -name '*.py' ! -path '*/migrations/*' \
	    -print0 | xargs -r0 bin/flake8

lint-css: sources = src/maasserver/static/css
lint-css: /usr/bin/pocketlint
	@find $(sources) -type f \
	    -print0 | xargs -r0 pocketlint --max-length=120

lint-js: sources = src/maasserver/static/js
lint-js: /usr/bin/pocketlint
	@find $(sources) -type f -print0 | xargs -r0 pocketlint

/usr/bin/pocketlint:
	sudo apt-get install python-pocket-lint

check: clean test

docs/api.rst: bin/maas src/maasserver/api.py syncdb
	bin/maas generate_api_doc > $@

sampledata: bin/maas syncdb
	bin/maas loaddata src/maasserver/fixtures/dev_fixture.yaml

doc: bin/sphinx docs/api.rst
	bin/sphinx

clean:
	find . -type f -name '*.py[co]' -print0 | xargs -r0 $(RM)
	find . -type f -name '*~' -print0 | xargs -r0 $(RM)
	$(RM) -r media/demo/* media/development

distclean: clean shutdown
	utilities/maasdb delete-cluster ./db/
	$(RM) -r eggs develop-eggs
	$(RM) -r bin build dist logs/* parts
	$(RM) tags TAGS .installed.cfg
	$(RM) -r *.egg *.egg-info src/*.egg-info
	$(RM) docs/api.rst
	$(RM) -r docs/_build/
	$(RM) -r run/* services/*/supervise
	$(RM) twisted/plugins/dropin.cache

harness: bin/maas dev-db
	bin/maas shell --settings=maas.demo

syncdb: bin/maas dev-db
	bin/maas syncdb --noinput
	bin/maas migrate maasserver --noinput
	bin/maas migrate metadataserver --noinput

define phony_targets
  build
  check
  clean
  dev-db
  distclean
  doc
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

service_names := pserv reloader txlongpoll web webapp
services := $(patsubst %,services/%/,$(service_names))

run:
	@services/run $(service_names)

run+webapp:
	@services/run $(service_names) +webapp

start: $(addsuffix @start,$(services))

stop: $(addsuffix @stop,$(services))

status: $(addsuffix @status,$(services))

restart: $(addsuffix @restart,$(services))

shutdown: $(addsuffix @shutdown,$(services))

supervise: $(addsuffix @supervise,$(services))

define phony_services_targets
  restart
  run
  run+webapp
  shutdown
  start
  status
  stop
  supervise
endef

# Pseudo-magic targets for controlling individual services.

service_lock = setlock -n /run/lock/maas.dev.$(firstword $(1))

services/%/@run: services/%/@shutdown services/%/@deps
	@$(call service_lock, $*) services/$*/run

services/%/@start: services/%/@supervise
	@svc -u $(@D)

services/%/@stop: services/%/@supervise
	@svc -d $(@D)

services/%/@status:
	@svstat $(@D)

services/%/@restart: services/%/@supervise
	@svc -du $(@D)

services/%/@shutdown:
	@if svok $(@D); then svc -dx $(@D); fi
	@while svok $(@D); do sleep 0.1; done

services/%/@supervise: services/%/@deps
	@mkdir -p logs/$*
	@touch $(@D)/down
	@if ! svok $(@D); then \
	    logdir=$(PWD)/logs/$* \
	        $(call service_lock, $*) supervise $(@D) & fi
	@while ! svok $(@D); do sleep 0.1; done

# Dependencies for individual services.

services/pserv/@deps: bin/twistd.pserv

services/reloader/@deps:

services/txlongpoll/@deps: bin/twistd.txlongpoll

services/web/@deps:

services/webapp/@deps: bin/maas dev-db

#
# Phony stuff.
#

define phony
  $(phony_services_targets)
  $(phony_targets)
endef

phony := $(sort $(strip $(phony)))

.PHONY: $(phony)
