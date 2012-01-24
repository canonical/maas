PYTHON = python2.7

build: bin/buildout bin/django doc

bin/buildout: bootstrap.py distribute_setup.py
	$(PYTHON) bootstrap.py --distribute --setup-source distribute_setup.py
	@touch --no-create $@  # Ensure it's newer than its dependencies.

bin/django bin/test: bin/buildout buildout.cfg setup.py
	bin/buildout install django

bin/flake8: bin/buildout buildout.cfg setup.py
	bin/buildout install flake8

bin/sphinx: bin/buildout buildout.cfg setup.py
	bin/buildout install sphinx

dev-db:
	utilities/maasdb start ./db/ disposable

test: bin/test
	bin/test

lint: sources = setup.py src templates utilities
lint: bin/flake8
	@bin/flake8 $(sources) | \
	    (! fgrep -v "from maas.settings import *")

check: clean test

docs/api.rst: bin/django src/maasserver/api.py
	bin/django gen_rst_api_doc > $@

sampledata: bin/django
	bin/django loaddata src/maasserver/fixtures/dev_fixture.yaml

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

run: bin/django dev-db
	bin/django runserver 8000

harness: bin/django dev-db
	bin/django shell

syncdb: bin/django dev-db
	bin/django syncdb

.PHONY: \
    build check clean dev-db distclean doc \
    harness lint run syncdb test sampledata
