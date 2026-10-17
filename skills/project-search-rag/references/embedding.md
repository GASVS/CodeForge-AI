# Chunking & Embedding Strategy

**Chunking**
- 800‑character windows with 200‑character overlap.
- Split on blank lines first, then fallback to windowing.
- Lines >10 KB are hard‑split into multiple non‑overlapping chunks of 10 KB.

**Embedding**
- Use Ollama local model (`nomic-embed-text`) via `/api/embeddings`.
- Batch size 16, limit payload 512 KB.
- Store in SQLite `embeddings` table with `project_id`, `file_id`, `chunk_text`, `embedding` columns.
- Delete existing embeddings for project before inserting to keep idempotent indices.
