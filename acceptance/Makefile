include /etc/lsb-release

packaging := lp:~maas-maintainers/maas/packaging

# Special-case Precise.
ifeq ($(DISTRIB_CODENAME),precise)
packaging := $(packaging).precise
endif

upstream := $(abspath ..)
packages = $(abspath $(wildcard *.deb))
image := maas-$(DISTRIB_CODENAME)

##

define ephexec
sudo LC_ALL=C SSH_ASKPASS=$(abspath ubuntupass) setsid \
    lxc-start-ephemeral -b $(abspath .) -o $(image) -u ubuntu -- \
    DEBIAN_FRONTEND=noninteractive SUDO_ASKPASS=$(abspath ubuntupass)
endef

define ephexec-make
$(ephexec) $(abspath with-make) make -C $(abspath .)
endef

define check-service
test $(2) = $(wordlist 2,2,$(shell service $(1) status))  # $(1)
endef

##

test: services sudo image build
	$(ephexec-make) $@-inner

build: services sudo image source source/debian
	$(ephexec-make) $@-inner

image: /var/lib/lxc/$(image)

services:
	$(call check-service,lxc,start/running)
	$(call check-service,lxc-net,start/running)

define phony-outer-targets
  build
  image
  services
  test
endef

##

test-inner: upgrade-inner
	sudo -AE dpkg --install -- $(packages)
	sudo -AE apt-get --fix-broken --assume-yes install

build-inner: upgrade-inner
	sudo -AE apt-get --assume-yes install devscripts debhelper dh-apport
	cd source && debuild -i -us -uc -b

upgrade-inner:
	sudo -AE apt-get --assume-yes update
	sudo -AE apt-get --assume-yes upgrade

define phony-inner-targets
  build-inner
  test-inner
  upgrade-inner
endef

##

source:
	bzr export --uncommitted $@ $(upstream)

source/debian: | source
	bzr export $@ $(packaging)/debian

/var/lib/lxc/$(image): sudo
	sudo lxc-create -n $(image) -t ubuntu

##

sudo:
	@sudo -v

clean:
	$(RM) -r source *.build *.changes *.deb

define phony-misc-targets
  clean
  sudo
endef

##

define phony
  $(phony-inner-targets)
  $(phony-misc-targets)
  $(phony-outer-targets)
endef

phony := $(sort $(strip $(phony)))

.PHONY: $(phony)
