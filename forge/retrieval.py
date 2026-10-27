from __future__ import annotations

import hashlib
import math
import os
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .workspace import Workspace

TOKEN_RE = re.compile(r"[a-zA-Z_][a-zA-Z0-9_]{1,}")
CODE_SUFFIXES = {
    ".py", ".pyi", ".js", ".jsx", ".ts", ".tsx", ".java", ".go", ".rs",
    ".cpp", ".cc", ".c", ".h", ".hpp", ".cs", ".rb", ".php", ".swift",
    ".kt", ".sql", ".sh", ".yaml", ".yml", ".toml", ".json", ".md",
}
MAX_FILE_BYTES = 250_000


@dataclass(frozen=True)
class CodeChunk:
    chunk_id: str
    path: str
    start_line: int
    end_line: int
    text: str
    tokens: tuple[str, ...]


class CodeRetriever:
    """Repository code retriever: BM25 by default, optional Chroma dense retrieval.

    The default path is offline and requires no model download. Set
    FORGE_USE_CHROMA=1 and install the vector extra to blend lexical and vector
    ranks using reciprocal-rank fusion.
    """

    def __init__(self, root: str | Path) -> None:
        self.workspace = Workspace(root)
        self.use_chroma = os.getenv("FORGE_USE_CHROMA", "0").strip() == "1"
        self._chunks: list[CodeChunk] | None = None
        self._mode = "bm25"

    @property
    def mode(self) -> str:
        return self._mode

    @staticmethod
    def _tokens(text: str) -> tuple[str, ...]:
        return tuple(token.casefold() for token in TOKEN_RE.findall(text))

    def _build(self) -> list[CodeChunk]:
        if self._chunks is not None:
            return self._chunks

        chunks: list[CodeChunk] = []
        for relative in self.workspace.list_files(limit=800):
            if Path(relative).suffix.casefold() not in CODE_SUFFIXES:
                continue
            try:
                text = self.workspace.read(relative, max_bytes=MAX_FILE_BYTES)
            except (OSError, ValueError, PermissionError):
                continue
            lines = text.splitlines()
            if not lines:
                continue

            window, overlap = 55, 8
            step = window - overlap
            for start in range(0, len(lines), step):
                snippet = "\n".join(lines[start:start + window]).strip()
                if not snippet:
                    continue
                start_line = start + 1
                end_line = min(start + window, len(lines))
                digest = hashlib.sha1(
                    f"{relative}:{start_line}:{snippet}".encode("utf-8")
                ).hexdigest()
                chunks.append(CodeChunk(
                    chunk_id=digest,
                    path=relative,
                    start_line=start_line,
                    end_line=end_line,
                    text=snippet[:8_000],
                    tokens=self._tokens(snippet),
                ))
                if len(chunks) >= 5_000:
                    break
            if len(chunks) >= 5_000:
                break

        self._chunks = chunks
        return chunks

    @staticmethod
    def _bm25(query_tokens: tuple[str, ...], chunks: list[CodeChunk]) -> list[tuple[CodeChunk, float]]:
        if not chunks or not query_tokens:
            return []
        document_frequency: Counter[str] = Counter()
        lengths = []
        token_counts: list[Counter[str]] = []
        for chunk in chunks:
            counts = Counter(chunk.tokens)
            token_counts.append(counts)
            lengths.append(len(chunk.tokens))
            document_frequency.update(counts.keys())

        total_docs = len(chunks)
        avg_length = max(sum(lengths) / total_docs, 1.0)
        k1, b = 1.5, 0.75
        scored: list[tuple[CodeChunk, float]] = []
        for chunk, counts, length in zip(chunks, token_counts, lengths):
            score = 0.0
            for token in query_tokens:
                tf = counts.get(token, 0)
                if not tf:
                    continue
                df = document_frequency[token]
                idf = math.log(1.0 + (total_docs - df + 0.5) / (df + 0.5))
                denominator = tf + k1 * (1.0 - b + b * length / avg_length)
                score += idf * (tf * (k1 + 1.0)) / denominator
            if score > 0:
                scored.append((chunk, score))
        return sorted(scored, key=lambda item: item[1], reverse=True)

    def _chroma_ranks(self, chunks: list[CodeChunk], query: str, limit: int) -> list[str]:
        import chromadb  # optional dependency

        store_path = self.workspace.root / ".forge" / "chroma"
        store_path.mkdir(parents=True, exist_ok=True)
        client = chromadb.PersistentClient(path=str(store_path))
        collection = client.get_or_create_collection(
            name="forge-code",
            metadata={"hnsw:space": "cosine"},
        )
        if chunks:
            collection.upsert(
                ids=[chunk.chunk_id for chunk in chunks],
                documents=[chunk.text for chunk in chunks],
                metadatas=[{
                    "path": chunk.path,
                    "start_line": chunk.start_line,
                    "end_line": chunk.end_line,
                } for chunk in chunks],
            )
        result: dict[str, Any] = collection.query(
            query_texts=[query],
            n_results=min(max(limit * 3, limit), len(chunks)),
            include=["distances"],
        )
        return list((result.get("ids") or [[]])[0])

    def search(self, query: str, limit: int = 8) -> list[dict[str, Any]]:
        query = query.strip()
        if not query or len(query) > 500:
            raise ValueError("query must be 1-500 characters")
        if limit < 1 or limit > 20:
            raise ValueError("limit must be between 1 and 20")

        chunks = self._build()
        query_tokens = self._tokens(query)
        lexical = self._bm25(query_tokens, chunks)[:max(limit * 3, limit)]
        if not lexical:
            self._mode = "bm25"
            return []

        fused_scores = {chunk.chunk_id: 1.0 / (60 + rank)
                        for rank, (chunk, _) in enumerate(lexical, start=1)}
        by_id = {chunk.chunk_id: chunk for chunk in chunks}
        self._mode = "bm25"

        if self.use_chroma:
            try:
                vector_ids = self._chroma_ranks(chunks, query, limit)
                for rank, chunk_id in enumerate(vector_ids, start=1):
                    fused_scores[chunk_id] = fused_scores.get(chunk_id, 0.0) + 1.0 / (60 + rank)
                if vector_ids:
                    self._mode = "hybrid-bm25+chroma"
            except Exception:
                # The offline lexical path remains available when the optional
                # vector dependency/model is not installed or cannot initialize.
                self._mode = "bm25-fallback"

        ranked = sorted(fused_scores.items(), key=lambda item: item[1], reverse=True)[:limit]
        return [{
            "path": by_id[chunk_id].path,
            "start_line": by_id[chunk_id].start_line,
            "end_line": by_id[chunk_id].end_line,
            "score": round(score, 6),
            "text": by_id[chunk_id].text,
            "mode": self._mode,
        } for chunk_id, score in ranked if chunk_id in by_id]
