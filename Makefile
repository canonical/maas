PYTHON = python2.7

build: bin/buildout bin/maas bin/test.maas bin/test.pserv bin/py bin/ipy

all: build doc

bin/buildout: bootstrap.py distribute_setup.py
	$(PYTHON) bootstrap.py --distribute --setup-source distribute_setup.py
	@touch --no-create $@  # Ensure it's newer than its dependencies.

bin/maas bin/test.maas: bin/buildout buildout.cfg setup.py
	bin/buildout install maas

bin/test.pserv: bin/buildout buildout.cfg setup.py
	bin/buildout install pserv-test

bin/flake8: bin/buildout buildout.cfg setup.py
	bin/buildout install flake8

bin/sphinx: bin/buildout buildout.cfg setup.py
	bin/buildout install sphinx

bin/py bin/ipy: bin/buildout buildout.cfg setup.py
	bin/buildout install repl

dev-db:
	utilities/maasdb start ./db/ disposable

test: bin/test.maas bin/test.pserv
	bin/test.maas
	bin/test.pserv

lint: sources = setup.py src templates utilities
lint: bin/flake8
	@bin/flake8 $(sources) | \
	    (! fgrep -v "from maas.settings import *")

check: clean test

docs/api.rst: bin/maas src/maasserver/api.py
	bin/maas generate_api_doc > $@

sampledata: bin/maas
	bin/maas loaddata src/maasserver/fixtures/dev_fixture.yaml

doc: bin/sphinx docs/api.rst
	bin/sphinx

clean:
	find . -type f -name '*.py[co]' -print0 | xargs -r0 $(RM)
	find . -type f -name '*~' -print0 | xargs -r0 $(RM)

distclean: clean
	utilities/maasdb delete-cluster ./db/
	$(RM) -r eggs develop-eggs
	$(RM) -r bin build dist logs parts
	$(RM) tags TAGS .installed.cfg
	$(RM) -r *.egg *.egg-info src/*.egg-info
	$(RM) docs/api.rst
	$(RM) -r docs/_build/

run: bin/maas dev-db
	bin/maas runserver 8000

harness: bin/maas dev-db
	bin/maas shell

syncdb: bin/maas dev-db
	bin/maas syncdb

.PHONY: \
    build check clean dev-db distclean doc \
    harness lint run syncdb test sampledata
