-- Migration 005: Add pgvector embedding columns to content table
-- Requires: pgvector extension (CREATE EXTENSION vector)
-- Replaces: ChromaDB-based semantic search

-- Ensure pgvector extension is available
CREATE EXTENSION IF NOT EXISTS vector;

-- Add embedding columns to content table
-- One row = one content item = one embedding
ALTER TABLE content
  ADD COLUMN IF NOT EXISTS embedding vector(3072),
  ADD COLUMN IF NOT EXISTS embedding_model text,
  ADD COLUMN IF NOT EXISTS embedding_version text,
  ADD COLUMN IF NOT EXISTS embedding_source_hash text,
  ADD COLUMN IF NOT EXISTS embedding_updated_at timestamptz;

-- HNSW index will be created AFTER backfill completes
-- Creating after bulk writes produces a better-structured graph
-- Run after backfill:
--   CREATE INDEX idx_content_embedding_hnsw ON content USING hnsw (embedding vector_cosine_ops);
