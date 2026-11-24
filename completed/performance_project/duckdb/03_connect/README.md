## DESCRIBE vs. .schema
One difference between `DESCRIBE purchases` here and `.schema purchases`
in SQLite.

DESCRIBE purchaces in DuckDB returns the structure of a table, including column names, and data types.

.schema purchases displays the SQL statement used to create the table, including its columns, and indexes.