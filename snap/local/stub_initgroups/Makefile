LIB := stub_initgroups.so

.DEFAULT_GOAL := $(LIB)

%.so: %.c
	gcc -fPIC -shared -o $@ $< -ldl

install: $(LIB)
	install -t $(DESTDIR)/usr/lib -D $(LIB)
.PHONY: install
