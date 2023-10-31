BUILD_TYPE ?= snap
DOCSDIR := $(DESTDIR)/usr/share/maas/web/static/docs/

.DEFAULT_GOAL := install

install:
	git submodule update --init --remote src
	install -d $(DOCSDIR)
	cp -a src/production-html-$(BUILD_TYPE)/* $(DOCSDIR)
.PHONY: install
