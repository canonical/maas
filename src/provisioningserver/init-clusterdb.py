#!/usr/bin/env python

import provisioningserver
from maascli.config import ProfileConfig

# doesn't work - with ProfileConfig.open(CLUSTERD_DB_PATH) as config:
# NOTE!!  NOTE!! NOTE!!
#
#  JUST THROWING ALL SETTINGS IN clusterd.db FOR NOW!!
#  WILL SPLIT INTO regiond.db ONCE THINGS ARE WORKING!!!!!!
#
# NOTE!!  NOTE!! NOTE!!

with ProfileConfig.open('/var/lib/maas/clusterd.db') as config:
  config['resource_root'] = '/var/lib/maas/boot-resources/current/'
  config['CLUSTER_UUID']="a25a9557-5525-4c5d-9d98-b7c414c62ffe"
  config['MAAS_URL']='http://localhost:5240/MAAS'
  config['tftpport']=69
  config['DB_NAME'] = 'maasdb'
  config['DB_USER'] = 'maas' 
  config['DB_PASSWORD'] = ''
  config['DB_HOST'] = 'localhost'
  config['DB_ENGINE'] = 'django.db.backends.postgresql_psycopg2'