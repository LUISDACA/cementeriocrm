from django.db import migrations

SQL = """
CREATE FUNCTION cemetery_immutable_history() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'El historial y la auditoría son de solo inserción.';
END;
$$ LANGUAGE plpgsql;
CREATE TRIGGER cemetery_event_immutable BEFORE UPDATE OR DELETE ON cemetery_event
FOR EACH ROW EXECUTE FUNCTION cemetery_immutable_history();
CREATE TRIGGER cemetery_audit_immutable BEFORE UPDATE OR DELETE ON cemetery_audit
FOR EACH ROW EXECUTE FUNCTION cemetery_immutable_history();
"""
REVERSE = """
DROP TRIGGER IF EXISTS cemetery_event_immutable ON cemetery_event;
DROP TRIGGER IF EXISTS cemetery_audit_immutable ON cemetery_audit;
DROP FUNCTION IF EXISTS cemetery_immutable_history();
"""


class Migration(migrations.Migration):
    dependencies = [("cemetery", "0001_initial")]
    operations = [migrations.RunSQL(SQL, REVERSE)]
