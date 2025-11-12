from django.core.management.base import BaseCommand
from django.db import connections

INDEXES = [
    # radius.radacct
    {
        'schema': 'radius', 'table': 'radacct', 'name': 'idx_radacct_username_stoptime',
        'ddl': 'CREATE INDEX idx_radacct_username_stoptime ON radius.radacct (username, acctstoptime)'
    },
    {
        'schema': 'radius', 'table': 'radacct', 'name': 'idx_radacct_nasip_stoptime',
        'ddl': 'CREATE INDEX idx_radacct_nasip_stoptime ON radius.radacct (nasipaddress, acctstoptime)'
    },
    {
        'schema': 'radius', 'table': 'radacct', 'name': 'idx_radacct_starttime',
        'ddl': 'CREATE INDEX idx_radacct_starttime ON radius.radacct (acctstarttime)'
    },
    {
        'schema': 'radius', 'table': 'radacct', 'name': 'idx_radacct_username_starttime',
        'ddl': 'CREATE INDEX idx_radacct_username_starttime ON radius.radacct (username, acctstarttime)'
    },
    # radius.radcheck
    {
        'schema': 'radius', 'table': 'radcheck', 'name': 'idx_radcheck_username_attr',
        'ddl': 'CREATE INDEX idx_radcheck_username_attr ON radius.radcheck (username, attribute)'
    },
    # titan.tbl_agent3
    {
        'schema': 'titan', 'table': 'tbl_agent3', 'name': 'idx_agent3_hostip',
        'ddl': 'CREATE INDEX idx_agent3_hostip ON titan.tbl_agent3 (hostip)'
    },
    {
        'schema': 'titan', 'table': 'tbl_agent3', 'name': 'idx_agent3_active_status',
        'ddl': 'CREATE INDEX idx_agent3_active_status ON titan.tbl_agent3 (is_active, is_status)'
    },
    {
        'schema': 'titan', 'table': 'tbl_agent3', 'name': 'idx_agent3_protocol',
        'ddl': "CREATE INDEX idx_agent3_protocol ON titan.tbl_agent3 (protocol)"
    },
    {
        'schema': 'titan', 'table': 'tbl_agent3', 'name': 'idx_agent3_auto_flags',
        'ddl': 'CREATE INDEX idx_agent3_auto_flags ON titan.tbl_agent3 (is_auto_ct, is_auto_cm, is_auto_cu, is_auto)'
    },
    {
        'schema': 'titan', 'table': 'tbl_agent3', 'name': 'idx_agent3_name',
        'ddl': 'CREATE INDEX idx_agent3_name ON titan.tbl_agent3 (name)'
    },
]

class Command(BaseCommand):
    help = 'Add recommended performance indexes if they are missing (idempotent).'

    def handle(self, *args, **options):
        conn = connections['default']
        with conn.cursor() as cur:
            for idx in INDEXES:
                schema = idx['schema']
                table = idx['table']
                name = idx['name']
                ddl = idx['ddl']
                try:
                    cur.execute(
                        """
                        SELECT COUNT(1) FROM information_schema.statistics
                        WHERE table_schema = DATABASE() AND table_name = %s AND index_name = %s
                        """,
                        [table, name]
                    )
                    exists = cur.fetchone()[0] > 0
                    if exists:
                        self.stdout.write(self.style.WARNING(f"[SKIP] {schema}.{table}:{name} exists"))
                        continue
                    self.stdout.write(f"[CREATE] {schema}.{table}:{name}")
                    cur.execute(ddl)
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"[FAIL] {schema}.{table}:{name} -> {e}"))
                    conn.rollback()
                else:
                    conn.commit()
                    self.stdout.write(self.style.SUCCESS(f"[OK] {schema}.{table}:{name}"))
