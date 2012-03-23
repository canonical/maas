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

distclean: clean pserv-stop txlongpoll-stop
	utilities/maasdb delete-cluster ./db/
	$(RM) -r eggs develop-eggs
	$(RM) -r bin build dist logs/* parts
	$(RM) tags TAGS .installed.cfg
	$(RM) -r *.egg *.egg-info src/*.egg-info
	$(RM) docs/api.rst
	$(RM) -r docs/_build/

run/pserv.pid: | bin/twistd.pserv etc/pserv.yaml
	bin/twistd.pserv --logfile=/dev/null --pidfile=$@ \
	    maas-pserv --config-file=etc/pserv.yaml

pserv-start: run/pserv.pid

pserv-stop: pidfile=run/pserv.pid
pserv-stop:
	{ test -e $(pidfile) && cat $(pidfile); } | xargs --no-run-if-empty kill

run/txlongpoll.pid: | bin/twistd.txlongpoll etc/txlongpoll.yaml
	bin/twistd.txlongpoll --logfile=/dev/null --pidfile=$@ \
	    txlongpoll --config-file=etc/txlongpoll.yaml

txlongpoll-start: run/txlongpoll.pid

txlongpoll-stop: pidfile=run/txlongpoll.pid
txlongpoll-stop:
	{ test -e $(pidfile) && cat $(pidfile); } | xargs --no-run-if-empty kill

run: bin/maas dev-db run/pserv.pid run/txlongpoll.pid
	bin/maas runserver 0.0.0.0:5240 --settings=maas.demo

harness: bin/maas dev-db
	bin/maas shell --settings=maas.demo

syncdb: bin/maas dev-db
	bin/maas syncdb --noinput
	bin/maas migrate maasserver --noinput
	bin/maas migrate metadataserver --noinput

checkbox: config=checkbox/plugins/jobs_info/directories=$(PWD)/qa/checkbox
checkbox:
	checkbox-gtk --config=$(config) --whitelist-file=

.PHONY: \
    build check checkbox clean dev-db distclean doc \
    harness lint pserv-start pserv-stop run \
    txlongpoll-start txlongpoll-stop \
    syncdb test sampledata
