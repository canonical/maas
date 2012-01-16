PYTHON_SRC := $(shell find src -name '*.py' )
PYTHON = python

build: bin/buildout

bin/buildout: buildout.cfg setup.py
	$(PYTHON) bootstrap.py
	bin/buildout
	@touch bin/buildout

test:
	bin/test

lint:
	pyflakes $(PYTHON_SRC)
	pylint --rcfile=etc/pylintrc $(PYTHON_SRC)

check: clean bin/buildout
	bin/test

clean:
	find . -type f -name '*.py[co]' -exec rm -f {} \;
	#rm -f bin/buildout
	#bzr clean-tree --unknown --force

realclean: clean
	rm -rf download-cache
	rm -rf eggs
	rm -rf develop-eggs

tags:
	bin/tags

run:
	bin/django runserver 8000

harness:
	. bin/maasdb.sh ; maasdb_init_db db/development disposable
	bin/django shell

syncdb:
	bin/django syncdb
