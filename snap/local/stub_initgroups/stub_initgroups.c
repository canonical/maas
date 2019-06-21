#define _GNU_SOURCE
#include <dlfcn.h>
#include <sys/types.h>
#include <stdio.h>

typedef int (*orig_setgroups_f_type)(size_t, const gid_t *);

int setgroups(size_t size, const gid_t *list) {
  orig_setgroups_f_type orig_setgroups;
  orig_setgroups = (orig_setgroups_f_type)dlsym(RTLD_NEXT, "setgroups");
  return orig_setgroups(0, NULL);
}

// this is only needed until there's proper support in snapd for initgroups()
// see https://forum.snapcraft.io/t/seccomp-filtering-for-setgroups/2109 for
// more info.
int initgroups(const char *user, gid_t group) {
  return setgroups(0, NULL);
}
