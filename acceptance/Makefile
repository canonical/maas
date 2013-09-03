#
# Build and test everything in ephemeral containers:
#
#   $ make
#
# Use a different packaging branch:
#
#   $ make packaging=/path/to/branch
#
# Note: /path/to/branch can be anything that bzr recognises, so an lp:
# link, or bzr+ssh, and so on.
#
# Build and test with a different Ubuntu series:
#
#   $ make series=randy
#

include /etc/lsb-release

# Default to the newer of Quantal or the local series.
series := $(lastword $(sort quantal $(DISTRIB_CODENAME)))

# Default to the main packaging branch on Launchpad, but treat Precise
# specially.
ifeq ($(series),precise)
packaging := lp:~maas-maintainers/maas/packaging.precise
else
packaging := lp:~maas-maintainers/maas/packaging
endif

# Assume we're testing this branch.
upstream := $(abspath ..)

# The container on which to base ephemerals.
container := maas-$(series)
containerdir := /var/lib/lxc/$(container)

## Convenience definitions.

define ephexec
sudo LC_ALL=C SSH_ASKPASS=$(abspath ubuntupass) setsid \
    lxc-start-ephemeral -b $(upstream) -o $(container) -u ubuntu -- \
    DEBIAN_FRONTEND=noninteractive SUDO_ASKPASS=$(abspath ubuntupass)
endef

define ephexec-make
$(ephexec) $(abspath with-make) make -C $(abspath .)
endef

define check-service
test $(2) = $(wordlist 2,2,$(shell initctl --system status $(1)))  # $(1)
endef

## Top-level targets.

test: build | services sudo container
	$(ephexec-make) $@-inner

# lxc-start-ephemeral does not return the exit code of any command it
# runs, so we delete any existing packages before building and check
# for their presence afterwards instead.
build: source source/debian | services sudo container
	@$(RM) *.deb
	$(ephexec-make) $@-inner
	@ls -1 *.deb
	@touch $@

container: $(containerdir)

container-update: $(containerdir) | services sudo
	$(abspath update-container) $(container)

services:
	$(call check-service,lxc,start/running)
	$(call check-service,lxc-net,start/running)

define phony-outer-targets
  container
  container-update
  services
  test
endef

## Targets that run within an LXC container.

# XXX: These packages appear to be missing from the dependencies
# declared in the packaging branch.
define missing-packages
  python-distribute
  python-django
endef

test-inner: upgrade-inner
	sudo -AE apt-get --assume-yes install $(strip $(missing-packages))
	sudo -AE dpkg --unpack --force-depends -- *.deb
	sudo -AE apt-get --fix-broken --assume-yes install

define build-packages
  debhelper
  devscripts
  dh-apport
endef

build-inner: | upgrade-inner
	sudo -AE apt-get --assume-yes install $(strip $(missing-packages))
	sudo -AE apt-get --assume-yes install $(strip $(build-packages))
	cd source && debuild -i -us -uc -b

upgrade-inner:
	sudo -AE apt-get --assume-yes update
	sudo -AE apt-get --assume-yes upgrade

define phony-inner-targets
  build-inner
  test-inner
  upgrade-inner
endef

## Dependencies.

source:
	bzr export --uncommitted $@ $(upstream)

source/debian: | source
	bzr export $@ $(packaging)/debian

$(containerdir): | services sudo
	sudo lxc-create -n $(container) \
	    -f /etc/lxc/default.conf -t ubuntu -- --release $(series)
	$(abspath update-container) $(container)

## Miscellaneous.

sudo:
	@sudo -v

clean:
	$(RM) -r source build *.build *.changes *.deb

define phony-misc-targets
  clean
  sudo
endef

## Phony.

define phony
  $(phony-inner-targets)
  $(phony-misc-targets)
  $(phony-outer-targets)
endef

phony := $(sort $(strip $(phony)))

.PHONY: $(phony)
