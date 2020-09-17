.DEFAULT_GOAL := src

src:
	git submodule update --init --remote

install: DOCSDIR = $(DESTDIR)/usr/share/maas/web/static/docs/
install: src
	install -d $(DOCSDIR)
	cp -a src/production-html/* $(DOCSDIR)
.PHONY: install
