-- Enable extensions on the default database and provision the test database.
-- This runs once when the data volume is first initialised.
CREATE EXTENSION IF NOT EXISTS hstore;
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS postgis;

SELECT 'CREATE DATABASE "history-mapped_test" WITH OWNER "history-mapped"'
WHERE NOT EXISTS (
	SELECT 1
	FROM pg_database
	WHERE datname = 'history-mapped_test'
) \gexec

\connect history-mapped_test

CREATE EXTENSION IF NOT EXISTS hstore;
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS postgis;
