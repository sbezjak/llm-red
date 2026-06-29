"""RagProvider - fires an attack at project 2 (the RAG system) as a SECONDARY target.

Project 0 has no document-ingestion surface, so the indirect-injection
family (a poisoned document the system ingests) has no real home there. The RAG
project does: it chunks documents into Chroma, retrieves over a query, and lets
an LLM answer from the retrieved chunks. That retrieve->generate path is exactly
where a buried instruction can cross from *data* into *command*.

This provider is the single seam that talks to the RAG system, the same role
TargetProvider plays for project 0. Two moves:

  1. ingest(documents)  - plant the poisoned doc in an EPHEMERAL Chroma
     collection (never the shipped .chroma index - we must not corrupt the RAG
     repo's persisted corpus; the constraint is that RAG is a secondary target,
     do not modify it).
  2. generate(query)    - retrieve over the planted corpus and run the RAG
     pipeline's own generator, returning the answer text the detector reads.

Why import the real llm_rag pipeline rather than reimplement it: a bypass only
counts as a RAG finding if it is the *actual* RAG code that obeyed the buried
note. So we call llm_rag.retrievers + llm_rag.generators directly. Those imports
are heavy (chromadb + sentence-transformers) and live behind the `rag` extra, so
they are imported lazily inside the methods - importing this module without the
extra installed is fine, only a live run needs it.
"""

from __future__ import annotations

import logging

from .base import Provider

logger = logging.getLogger(__name__)

# Mirrors llm_rag.scripts.build_index defaults so the planted corpus is embedded
# the same way the real index is. Kept here (not imported) so the constants are
# visible at the seam, the way TargetProvider mirrors project 0's few internals.
EMBED_MODEL = "all-MiniLM-L6-v2"
COLLECTION = "redteam_indirect_injection"


class RagProvider(Provider):
    """Ingest a (poisoned) document into an ephemeral RAG corpus, then query it.

    Holds one ephemeral Chroma collection for the life of the provider. `ingest`
    (re)builds it from the given documents; `generate` runs retrieve->generate
    over whatever is currently planted. The Ollama call happens inside the RAG
    pipeline's own OllamaProvider (HTTP to :11434), so contention with a running
    garak / other Ollama job applies - hold a live `generate` for a clear window.
    """

    def __init__(self, model: str = "llama3.2", k: int = 3) -> None:
        self.model = model
        self.k = k
        self._collection = None  # built lazily by ingest()

    def ingest(self, documents: list[str]) -> None:
        """Plant `documents` (one chunk each) in a fresh ephemeral collection.

        Ephemeral on purpose: no persistence, so the shipped RAG .chroma index
        is never touched. Each document becomes one chunk with a stable id so the
        retrieval log is readable. Pure local embedding work - no Ollama, safe to
        run while another Ollama job holds the backend.
        """
        import chromadb
        from chromadb.utils import embedding_functions

        # Ephemeral = vector store in RAM only, gone when the process exits (vs
        # PersistentClient(path=".chroma") = on disk = project 2's shipped corpus).
        # We use ephemeral so the planted poisoned doc never touches that real index.
        client = chromadb.EphemeralClient()
        try:
            client.delete_collection(COLLECTION)
        except Exception:
            pass
        ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name=EMBED_MODEL)
        coll = client.create_collection(name=COLLECTION, embedding_function=ef)

        ids = [f"injected::doc::{i}" for i in range(len(documents))]
        coll.add(
            ids=ids,
            documents=documents,
            metadatas=[{"source": "ingested", "section": "(document)"} for _ in documents],
        )
        self._collection = coll
        logger.info("RagProvider ingested %d document(s) into %r", len(documents), COLLECTION)

    async def generate(self, prompt: str) -> str:
        """Run the RAG pipeline over `prompt` (the user query) and return the answer.

        `prompt` is the *question* a victim user would ask; the poisoned content
        was planted by a prior `ingest`. Delegates retrieval and generation to
        the real llm_rag code so a bypass is a genuine RAG-system finding. The
        full prompt + answer are logged at INFO by llm_rag's own components; we
        log the query and final answer here too so the seam is visible in the
        report.
        """
        if self._collection is None:
            raise RuntimeError("RagProvider.generate called before ingest(); plant a doc first")

        from llm_rag.generators.generate import generate_answer
        from llm_rag.providers.ollama import OllamaProvider
        from llm_rag.retrievers.vector import vector_retrieve

        logger.info("RagProvider query: %s", prompt)
        chunks = vector_retrieve(prompt, self.k, self._collection)
        result = await generate_answer(prompt, chunks, OllamaProvider(model=self.model))
        logger.info("RagProvider answer:\n%s", result.answer)
        return result.answer
