#!/usr/bin/env python3
import os
import sys
import django
from django.db import connections

# Ensure we can import Django settings
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'main.settings')
sys.path.insert(0, BASE_DIR)

django.setup()

SQLS = [
    # Create with explicit column order relative to is_auto
    "ALTER TABLE titan.tbl_agent3 ADD COLUMN is_auto_ct TINYINT(1) NOT NULL DEFAULT 0 AFTER is_auto",
    "ALTER TABLE titan.tbl_agent3 ADD COLUMN is_auto_cm TINYINT(1) NOT NULL DEFAULT 0 AFTER is_auto_ct",
    "ALTER TABLE titan.tbl_agent3 ADD COLUMN is_auto_cu TINYINT(1) NOT NULL DEFAULT 0 AFTER is_auto_cm",
]

CHECKS = {
    'is_auto_ct': "SELECT COUNT(*) AS cnt FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'tbl_agent3' AND COLUMN_NAME = 'is_auto_ct'",
    'is_auto_cm': "SELECT COUNT(*) AS cnt FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'tbl_agent3' AND COLUMN_NAME = 'is_auto_cm'",
    'is_auto_cu': "SELECT COUNT(*) AS cnt FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'tbl_agent3' AND COLUMN_NAME = 'is_auto_cu'",
}


def column_exists(cur, column_name: str) -> bool:
    cur.execute(CHECKS[column_name])
    row = cur.fetchone()
    # row as tuple or dict depending on backend; normalize
    cnt = row[0] if isinstance(row, (list, tuple)) else row.get('cnt', 0)
    try:
        return int(cnt) > 0
    except Exception:
        return False


def main():
    with connections['default'].cursor() as cur:
        to_create = []
        for idx, col in enumerate(['is_auto_ct', 'is_auto_cm', 'is_auto_cu']):
            try:
                if column_exists(cur, col):
                    print(f"INFO -> Column already exists: {col}")
                else:
                    to_create.append((col, SQLS[idx]))
            except Exception as e:
                print(f"WARN -> Column check failed for {col}: {e}")
        for col, sql in to_create:
            try:
                print(f"INFO -> Creating column {col} ...")
                cur.execute(sql)
                print(f"INFO -> Created column {col}")
            except Exception as e:
                print(f"ERROR -> Failed to create column {col}: {e}")
        # Ensure column order even when columns already existed
        try:
            print("INFO -> Ensuring column order AFTER is_auto ...")
            cur.execute("ALTER TABLE titan.tbl_agent3 MODIFY COLUMN is_auto_ct TINYINT(1) NOT NULL DEFAULT 0 AFTER is_auto")
            cur.execute("ALTER TABLE titan.tbl_agent3 MODIFY COLUMN is_auto_cm TINYINT(1) NOT NULL DEFAULT 0 AFTER is_auto_ct")
            cur.execute("ALTER TABLE titan.tbl_agent3 MODIFY COLUMN is_auto_cu TINYINT(1) NOT NULL DEFAULT 0 AFTER is_auto_cm")
            print("INFO -> Column order ensured: is_auto -> is_auto_ct -> is_auto_cm -> is_auto_cu")
        except Exception as e:
            print(f"WARN -> Could not enforce column order: {e}")
        if not to_create:
            print('INFO -> All telecom auto columns already present')


if __name__ == '__main__':
    main()
