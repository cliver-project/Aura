-- Runs once on an empty PostgreSQL data volume.
-- The default database (aura) already exists via POSTGRES_DB; Gitea gets its
-- own database in the same cluster.

SELECT 'CREATE DATABASE gitea OWNER aura'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'gitea')\gexec
