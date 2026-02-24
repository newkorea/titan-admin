import MySQLdb

config = {
  'user': 'titan',
  'passwd': 'xkdlxks12!@',
  'host': '218.158.57.48',
  'db': 'titan',
  'charset': 'utf8mb4'
}

try:
    cnx = MySQLdb.connect(**config)
    cursor = cnx.cursor()

    # Create table
    table_sql = """
    CREATE TABLE IF NOT EXISTS tbl_global_config (
        config_key VARCHAR(50) PRIMARY KEY,
        config_value VARCHAR(255) NOT NULL,
        description VARCHAR(255),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """
    cursor.execute(table_sql)
    print("Table tbl_global_config checked/created.")

    # Insert defaults
    defaults = [
        ('wechat_enabled', 'true', 'Enable WeChat Pay'),
        ('alipay_enabled', 'true', 'Enable AliPay')
    ]

    for key, val, desc in defaults:
        cursor.execute("SELECT config_key FROM tbl_global_config WHERE config_key = %s", (key,))
        if not cursor.fetchone():
            cursor.execute("INSERT INTO tbl_global_config (config_key, config_value, description) VALUES (%s, %s, %s)", (key, val, desc))
            print(f"Inserted default for {key}")
        else:
            print(f"Config {key} already exists.")

    cnx.commit()
    cursor.close()
    cnx.close()
    print("Database setup complete.")

except Exception as err:
    print(f"Error: {err}")
