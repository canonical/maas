PYTHON = python2.7

build: bin/buildout bin/django doc

bin/buildout: bootstrap.py
	$(PYTHON) bootstrap.py

bin/django bin/django-python bin/test: bin/buildout buildout.cfg setup.py
	bin/buildout

dev-db:
	bin/maasdb start ./db/ disposable

test: bin/test
	bin/test

lint: sources = setup.py src templates utilities
lint:
	@(pyflakes $(sources); pep8 --repeat $(sources)) | sort -g

check: clean test

api-doc: bin/django src/maasserver/api.py
	bin/django gen_rst_api_doc > docs/api.rst

doc: api-doc
	$(MAKE) -C docs html

clean:
	find . -type f -name '*.py[co]' -print0 | xargs -r0 $(RM)
	$(RM) bin/buildout bin/django bin/django-python bin/test

distclean: clean
	bin/maasdb delete-cluster ./db/
	$(RM) -r eggs develop-eggs
	$(RM) -r build logs parts
	$(RM) tags TAGS .installed.cfg
	$(RM) *.egg *.egg-info
	$(RM) docs/api.rst/
	$(RM) -r docs/_build/

run: bin/django dev-db
	bin/django runserver 8000

harness: bin/django dev-db
	bin/django shell

syncdb: bin/django dev-db
	bin/django syncdb

.PHONY: \
	build check clean dev-db distclean harness lint run syncdb \
	test doc
