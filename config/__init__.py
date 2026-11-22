try:
    import pymysql
except ImportError:  # SQLite-only setups do not need the MySQL driver.
    pymysql = None
else:
    pymysql.install_as_MySQLdb()
