-- Fuzzy searching within match names, using pg_trgm word similarity.
CREATE EXTENSION IF NOT EXISTS pg_trgm WITH SCHEMA public;

CREATE INDEX IF NOT EXISTS idx_match_name_trgm_gin
    ON public.match_series USING GIN (match_name public.gin_trgm_ops);
