-- Migration 006: padroniza coluna de embedding para VECTOR(768).
--
-- Contexto: a migration 001 criou a coluna como VECTOR(1536) (OpenAI),
-- mas o backend padrão é sentence-transformers (768 dims). Qualquer run
-- sem OpenAI tentava inserir vetores 768-dim numa coluna 1536-dim e falhava
-- silenciosamente, deixando a busca semântica vazia.
--
-- A solução é pinnar 768 dims (sentence-transformers) como padrão definitivo.
-- Os embeddings existentes precisam ser regerados após esta migration.

TRUNCATE TABLE embedding;

DROP INDEX IF EXISTS idx_embedding_ivfflat;

ALTER TABLE embedding ALTER COLUMN embedding TYPE vector(768);
