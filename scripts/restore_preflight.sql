SELECT
    (SELECT count(*)
       FROM pg_class c JOIN pg_namespace n ON c.relnamespace = n.oid
      WHERE n.nspname NOT IN ('pg_catalog', 'information_schema')
        AND n.nspname NOT LIKE 'pg_toast%'
        AND n.nspname NOT LIKE 'pg_temp%'
        AND c.relkind IN ('r', 'p', 'v', 'm', 'S', 'f'))
  + (SELECT count(*)
       FROM pg_proc p JOIN pg_namespace n ON p.pronamespace = n.oid
      WHERE n.nspname NOT IN ('pg_catalog', 'information_schema')
        AND n.nspname NOT LIKE 'pg_%');
