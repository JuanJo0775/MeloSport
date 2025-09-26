-- Crear usuario (si no existe)
DO
$$
BEGIN
   IF NOT EXISTS (
      SELECT FROM pg_catalog.pg_roles WHERE rolname = 'melosport_user'
   ) THEN
      CREATE ROLE melosport_user LOGIN PASSWORD 'melosport@admin1010';
   END IF;
END
$$;

-- Crear base de datos (si no existe) y asignar propietario
DO
$$
BEGIN
   IF NOT EXISTS (
      SELECT FROM pg_catalog.pg_database WHERE datname = 'melosport_app'
   ) THEN
      PERFORM dblink_exec('dbname=' || current_database(),
        'CREATE DATABASE melosport_app OWNER melosport_user');
   END IF;
END
$$;

-- Conectarse a la base de datos melosport_app y activar extensiones
\c melosport_app
CREATE EXTENSION IF NOT EXISTS unaccent;
CREATE EXTENSION IF NOT EXISTS citext;



-- Crear usuario
CREATE ROLE melosport_user LOGIN PASSWORD 'melosport@admin1010';

-- Crear base de datos y asignar propietario
CREATE DATABASE melosport_app OWNER melosport_user;

-- Conectarse a la base de datos (hazlo en el Query Tool seleccionando melosport_app)
-- y luego ejecuta estas dos sentencias:
CREATE EXTENSION IF NOT EXISTS unaccent;
CREATE EXTENSION IF NOT EXISTS citext;
