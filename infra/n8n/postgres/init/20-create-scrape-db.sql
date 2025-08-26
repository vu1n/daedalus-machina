DO $$
BEGIN
   IF NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'n8n_scrape') THEN
      EXECUTE 'CREATE DATABASE n8n_scrape OWNER ' || current_user;
   END IF;
END
$$;
