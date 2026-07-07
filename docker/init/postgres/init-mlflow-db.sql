-- =============================================================================
-- RegulaForge - Initialize MLflow database on PostgreSQL startup
-- =============================================================================

-- Create MLflow database if using separate database
-- (Uncomment if you want a dedicated MLflow database)
-- CREATE DATABASE regulaforge_mlflow;

-- Create monitoring user (optional)
-- CREATE USER monitor WITH PASSWORD 'monitor_password';
-- GRANT CONNECT ON DATABASE regulaforge TO monitor;
-- GRANT USAGE ON SCHEMA public TO monitor;
-- GRANT SELECT ON ALL TABLES IN SCHEMA public TO monitor;
