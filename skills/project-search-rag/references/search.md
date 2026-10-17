# Cosine Similarity Rank Implementation

The RAG search endpoint uses **numpy** for efficient cosine similarity.

Algorithm:
1. Convert stored embeddings (floats) to a 2‑D NumPy array.
2. Normalize all vectors to unit norm.
3. For the query embedding, compute dot product with all stored embeddings.
4. Sort the resulting scores descending and slice the top `k`.

The endpoint returns each hit with file ID, start/end lines, and a 400‑char snippet (truncated if longer).
