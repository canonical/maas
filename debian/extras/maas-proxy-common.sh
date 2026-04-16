pre_start() {
  if [ ! -x /usr/sbin/squid ]; then
      echo "No squid binary found"
      exit 1
  fi
  SQUID=/usr/sbin/squid

  # ensure all cache dirs are there
  install -d -o proxy -g proxy -m 750 /var/cache/maas-proxy/
  install -d -o proxy -g proxy -m 750 /var/log/maas/proxy/
  install -m 750 -o proxy -g proxy -d /var/spool/maas-proxy/
  if [ -d /var/log/maas/proxy ]; then
   chown -R proxy:proxy /var/log/maas/proxy
  fi
  if [ -f /var/lib/maas/maas-proxy.conf ]; then
    if [ ! -d /var/cache/maas-proxy/00 ]; then
      $SQUID -z -d 5 -N -f /var/lib/maas/maas-proxy.conf
    fi
  fi
}
