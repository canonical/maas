from django.db import migrations

# At the time of writing this should match the old definition in
# maasserver.models.node.node_system_id, and vice-versa.
sequence_create = """\
DO
$$
BEGIN
    CREATE SEQUENCE maasserver_node_system_id_seq
    MINVALUE {minvalue:d} MAXVALUE {maxvalue:d}
    START WITH {start:d} NO CYCLE
    OWNED BY maasserver_node.system_id;
EXCEPTION WHEN duplicate_table THEN
    -- Do nothing, it already exists.
END
$$ LANGUAGE plpgsql;
""".format(
    # When converted using znum.to_int, 15600471 equals "4y3h7n" which is a
    # fairly garbled looking starting value; it'll hopefully prevent people
    # from immediately grokking that IDs are derived from a sequence. This
    # still allows for >175 million unique IDs.
    minvalue=(24**5),
    maxvalue=((24**6) - 1),
    start=15600471,
)

sequence_drop = "DROP SEQUENCE IF EXISTS maasserver_node_system_id_seq"


class Migration(migrations.Migration):
    dependencies = [("maasserver", "0067_add_size_to_largefile")]

    operations = [migrations.RunSQL(sequence_drop, sequence_create)]
