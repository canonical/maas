# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

REGIOND_DB_PATH = '/var/lib/maas/regiond.db'
REGIOND_DB_tftp_resource_root = "resource_root"
REGIOND_DB_tftpport = 'tftpport'
REDIOND_DB_static_root = 'STATIC_ROUTE'
REGIOND_DB_maas_url = 'MAAS_URL'
REDIOND_DB_db_password = 'DB_PASSWORD'
REDIOND_DB_db_username = 'DB_USER'

def get_region_variable(var):
    """Obtain the given environment variable from maas_cluster.conf.

    If the variable is not set, it probably means that whatever script
    started the current process neglected to run maas_cluster.conf.
    In that case, fail helpfully but utterly.
    """
    value = None
    from maascli.config import ProfileConfig
    with ProfileConfig.open(REGIOND_DB_PATH) as config:
        value = config[var]

    if value is None:
        raise AssertionError(
            "%s is not set.  This probably means that the script which "
            "started this program failed to source maas_cluster.conf."
            % var)
    return value

def set_region_variable(var, value):
    from maascli.config import ProfileConfig
    with ProfileConfig.open(REGIOND_DB_PATH) as config:
        config[var] = value
        
def get_maas_url():
    """Return the `maas url` setting."""
    return get_region_variable(REGIOND_DB_maas_url)

def get_tftp_resource_root():
    """Return the `tftp_resource_root` setting."""
    return get_region_variable(REGIOND_DB_tftp_resource_root)

def get_tftp_port():
    """Return the `tftp_port` setting."""
    return get_region_variable(REGIOND_DB_tftpport)


def get_tftp_generator():
    import os
    """Return the `tftp_generator` setting, which is maas url/api/1.0/pxeconfig/"""
    return os.path.join(get_maas_url(), 'api' , '1.0', 'pxeconfig')

def get_db_password():
    """Return the `db_password` setting."""
    return get_region_variable(REDIOND_DB_db_password)

def set_db_password(value):
    set_region_variable(REDIOND_DB_db_password, value)
    
def get_db_username():
    """Return the `db_username` setting."""
    return get_region_variable(REDIOND_DB_db_username)

def set_db_username(value):
    set_region_variable(REDIOND_DB_db_username, value)
    
def get_static_route():
    """Return the `static_route` setting."""
    return get_region_variable(REDIOND_DB_static_root)
