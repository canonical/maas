"""Migration for populating new Node fields related to constraints

A shared helper function is used that both the real Node model in maasserver
and the stubs used by south can work with. This saves writing the logic to
populate cpu_count and memory in two places. On migration it is likely that
tags do not exist yet.

If for whatever reason previously stored lshw output is not well formed XML,
the fields in Node are not populated.
"""
import math

from django.core.exceptions import ValidationError
from lxml import etree
from south.v2 import DataMigration


_xpath_processor_count = """\
    count(//node[@id='core']/
        node[@class='processor'][not(@disabled)])
"""

# Some machines have a <size> element in their memory <node> with the total
# amount of memory, and other machines declare the size of the memory in
# individual memory banks. This expression is mean to cope with both.
_xpath_memory_bytes = """\
    sum(//node[@id='memory']/size[@units='bytes'] |
        //node[starts-with(@id, 'memory:')]
            /node[starts-with(@id, 'bank:')]/size[@units='bytes'])
    div 1024 div 1024
"""

_xpath_storage_bytes = """\
    sum(//node[starts-with(@id, 'volume:')]/size[@units='bytes'])
    div 1024 div 1024
"""


def update_hardware_details(node, xmlbytes, tag_manager):
    """Set node hardware_details from lshw output and update related fields.

    This previously resided in `maasserver.models.node`, but has been
    copied into this migration so that it can be modified in its
    original location without breaking this migration.
    """
    try:
        doc = etree.XML(xmlbytes)
    except etree.XMLSyntaxError as e:
        raise ValidationError(
            {'hardware_details': ['Invalid XML: %s' % (e,)]})
    node.hardware_details = xmlbytes
    # Same document, many queries: use XPathEvaluator.
    evaluator = etree.XPathEvaluator(doc)
    cpu_count = evaluator(_xpath_processor_count)
    memory = evaluator(_xpath_memory_bytes)
    if not memory or math.isnan(memory):
        memory = 0
    storage = evaluator(_xpath_storage_bytes)
    if not storage or math.isnan(storage):
        storage = 0
    node.cpu_count = cpu_count or 0
    node.memory = memory
    node.storage = storage
    for tag in tag_manager.all():
        if not tag.definition:
            continue
        has_tag = evaluator(tag.definition)
        if has_tag:
            node.tags.add(tag)
        else:
            node.tags.remove(tag)
    node.save()


class Migration(DataMigration):

    _lshw_name = "01-lshw.out"

    def forwards(self, orm):
        """Move lshw text blob in metadataserver to xml field in Node"""
        Tag = orm['maasserver.tag']
        for commission_result in orm.NodeCommissionResult.objects.filter(
                name=self._lshw_name):
            node = commission_result.node
            data = commission_result.data
            try:
                update_hardware_details(node, data, Tag.objects)
            except ValidationError:
                pass
            else:
                node.save()

    def backwards(self, orm):
        """Move xml field in Node to lshw text blob in metadataserver"""
        Node = orm['maasserver.Node']
        for node in Node.objects.all():
            lshw_output = node.hardware_details
            if lshw_output:
                orm.NodeCommissionResult.objects.store_data(
                    node, self._lshw_name, lshw_output)

    models = {
        'auth.group': {
            'Meta': {'object_name': 'Group'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '80'}),
            'permissions': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['auth.Permission']", 'symmetrical': 'False', 'blank': 'True'})
        },
        'auth.permission': {
            'Meta': {'ordering': "('content_type__app_label', 'content_type__model', 'codename')", 'unique_together': "(('content_type', 'codename'),)", 'object_name': 'Permission'},
            'codename': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'content_type': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['contenttypes.ContentType']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '50'})
        },
        'auth.user': {
            'Meta': {'object_name': 'User'},
            'date_joined': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'email': ('django.db.models.fields.EmailField', [], {'unique': 'True', 'max_length': '75', 'blank': 'True'}),
            'first_name': ('django.db.models.fields.CharField', [], {'max_length': '30', 'blank': 'True'}),
            'groups': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['auth.Group']", 'symmetrical': 'False', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_active': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'is_staff': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'is_superuser': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'last_login': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'last_name': ('django.db.models.fields.CharField', [], {'max_length': '30', 'blank': 'True'}),
            'password': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'user_permissions': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['auth.Permission']", 'symmetrical': 'False', 'blank': 'True'}),
            'username': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '30'})
        },
        'contenttypes.contenttype': {
            'Meta': {'ordering': "('name',)", 'unique_together': "(('app_label', 'model'),)", 'object_name': 'ContentType', 'db_table': "'django_content_type'"},
            'app_label': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'model': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100'})
        },
        u'maasserver.node': {
            'Meta': {'object_name': 'Node'},
            'after_commissioning_action': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'architecture': ('django.db.models.fields.CharField', [], {'default': "u'i386/generic'", 'max_length': '31'}),
            'cpu_count': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'created': ('django.db.models.fields.DateTimeField', [], {}),
            'distro_series': ('django.db.models.fields.CharField', [], {'default': 'None', 'max_length': '10', 'null': 'True', 'blank': 'True'}),
            'error': ('django.db.models.fields.CharField', [], {'default': "u''", 'max_length': '255', 'blank': 'True'}),
            'hardware_details': ('maasserver.fields.XMLField', [], {'default': 'None', 'null': 'True', 'blank': 'True'}),
            'hostname': ('django.db.models.fields.CharField', [], {'default': "u''", 'max_length': '255', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'memory': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'netboot': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'nodegroup': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['maasserver.NodeGroup']", 'null': 'True'}),
            'owner': ('django.db.models.fields.related.ForeignKey', [], {'default': 'None', 'to': "orm['auth.User']", 'null': 'True', 'blank': 'True'}),
            'power_parameters': ('maasserver.fields.JSONObjectField', [], {'default': "u''", 'blank': 'True'}),
            'power_type': ('django.db.models.fields.CharField', [], {'default': "u''", 'max_length': '10', 'blank': 'True'}),
            'status': ('django.db.models.fields.IntegerField', [], {'default': '0', 'max_length': '10'}),
            'system_id': ('django.db.models.fields.CharField', [], {'default': "u'node-dc867442-0ca0-11e2-9ff0-fa163e46ecd0'", 'unique': 'True', 'max_length': '41'}),
            'tags': ('django.db.models.fields.related.ManyToManyField', [], {'to': u"orm['maasserver.Tag']", 'symmetrical': 'False'}),
            'token': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['piston.Token']", 'null': 'True'}),
            'updated': ('django.db.models.fields.DateTimeField', [], {})
        },
        u'maasserver.nodegroup': {
            'Meta': {'object_name': 'NodeGroup'},
            'api_key': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '18'}),
            'api_token': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['piston.Token']", 'unique': 'True'}),
            'created': ('django.db.models.fields.DateTimeField', [], {}),
            'dhcp_key': ('django.db.models.fields.CharField', [], {'default': "u''", 'max_length': '255', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '80', 'blank': 'True'}),
            'status': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'updated': ('django.db.models.fields.DateTimeField', [], {}),
            'uuid': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '36'})
        },
        u'maasserver.tag': {
            'Meta': {'object_name': 'Tag'},
            'comment': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'created': ('django.db.models.fields.DateTimeField', [], {}),
            'definition': ('django.db.models.fields.TextField', [], {}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '256'}),
            'updated': ('django.db.models.fields.DateTimeField', [], {})
        },
        u'metadataserver.nodecommissionresult': {
            'Meta': {'unique_together': "((u'node', u'name'),)", 'object_name': 'NodeCommissionResult'},
            'data': ('django.db.models.fields.CharField', [], {'max_length': '1048576'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'node': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['maasserver.Node']"})
        },
        u'metadataserver.nodekey': {
            'Meta': {'object_name': 'NodeKey'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'key': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '18'}),
            'node': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['maasserver.Node']", 'unique': 'True'}),
            'token': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['piston.Token']", 'unique': 'True'})
        },
        u'metadataserver.nodeuserdata': {
            'Meta': {'object_name': 'NodeUserData'},
            'data': ('metadataserver.fields.BinaryField', [], {}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'node': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['maasserver.Node']", 'unique': 'True'})
        },
        'piston.consumer': {
            'Meta': {'object_name': 'Consumer'},
            'description': ('django.db.models.fields.TextField', [], {}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'key': ('django.db.models.fields.CharField', [], {'max_length': '18'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'secret': ('django.db.models.fields.CharField', [], {'max_length': '32'}),
            'status': ('django.db.models.fields.CharField', [], {'default': "'pending'", 'max_length': '16'}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'consumers'", 'null': 'True', 'to': "orm['auth.User']"})
        },
        'piston.token': {
            'Meta': {'object_name': 'Token'},
            'callback': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
            'callback_confirmed': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'consumer': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['piston.Consumer']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_approved': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'key': ('django.db.models.fields.CharField', [], {'max_length': '18'}),
            'secret': ('django.db.models.fields.CharField', [], {'max_length': '32'}),
            'timestamp': ('django.db.models.fields.IntegerField', [], {'default': '1349189580L'}),
            'token_type': ('django.db.models.fields.IntegerField', [], {}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'tokens'", 'null': 'True', 'to': "orm['auth.User']"}),
            'verifier': ('django.db.models.fields.CharField', [], {'max_length': '10'})
        }
    }

    complete_apps = ['metadataserver']
    symmetrical = True
