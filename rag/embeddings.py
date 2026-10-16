import math
import hashlib
import re
from abc import ABC, abstractmethod
from typing import Any
import requests

SYNONYMS: dict[str, set[str]] = {
    "refund": {"return", "returns", "exchange", "money", "credit", "reimbursement"},
    "return": {"refund", "refunds", "exchange", "credit", "item"},
    "shipping": {"delivery", "ship", "shipment", "transit", "tracking", "courier", "package"},
    "delivery": {"shipping", "shipment", "transit", "courier", "package"},
    "policy": {"policies", "rules", "rule", "terms", "guidelines", "condition", "conditions"},
    "cost": {"price", "fee", "charge", "pricing", "rate"},
    "cancel": {"cancellation", "terminate", "stop", "abort"},
    "order": {"purchase", "item", "product", "package"}
}


def cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """
    Computes cosine similarity between two float vectors: (A . B) / (||A|| * ||B||).
    Returns value between -1.0 and 1.0 (or 0.0 if vectors are empty/zero).
    """
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0

    dot_product = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))

    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0

    return dot_product / (norm_a * norm_b)


def compute_lexical_score(query: str, document_text: str) -> float:
    """
    Calculates normalized keyword + synonym + phrase overlap score between query and document.
    Returns float in range [0.0, 1.0].
    """
    clean_query = query.lower().strip()
    clean_doc = document_text.lower().strip()

    query_tokens = [t for t in re.findall(r'\b\w+\b', clean_query) if len(t) > 2]
    doc_tokens = set(re.findall(r'\b\w+\b', clean_doc))

    if not query_tokens or not doc_tokens:
        return 0.0

    matches = 0.0
    for token in query_tokens:
        # Direct exact match
        if token in doc_tokens:
            matches += 1.0
            continue
        # Synonym match
        syns = SYNONYMS.get(token, set())
        if any(s in doc_tokens for s in syns):
            matches += 0.75
            continue
        # Stem prefix match
        if any(dt.startswith(token[:4]) for dt in doc_tokens if len(token) >= 4 and len(dt) >= 4):
            matches += 0.5

    # Bigram phrase bonus
    phrase_bonus = 0.0
    for i in range(len(query_tokens) - 1):
        phrase = f"{query_tokens[i]} {query_tokens[i+1]}"
        if phrase in clean_doc:
            phrase_bonus += 0.25

    base_score = matches / len(query_tokens)
    return min(1.0, base_score + phrase_bonus)


def compute_hybrid_score(
    query_vec: list[float],
    chunk_vec: list[float],
    query_text: str,
    chunk_text: str,
    vector_weight: float = 0.45,
    lexical_weight: float = 0.55
) -> float:
    """
    Combines dense semantic cosine similarity with BM25/lexical overlap
    for robust multi-tenant RAG retrieval.
    """
    cos_sim = max(0.0, cosine_similarity(query_vec, chunk_vec))
    lex_score = compute_lexical_score(query_text, chunk_text)
    return round((vector_weight * cos_sim) + (lexical_weight * lex_score), 4)


class BaseEmbeddingClient(ABC):
    @abstractmethod
    def embed(self, text: str) -> list[float]:
        pass

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [self.embed(t) for t in texts]


class DeterministicEmbeddingClient(BaseEmbeddingClient):
    """
    Zero-cost, offline semantic vectorizer producing 128-dimensional normalized term frequency vectors.
    Uses stemmed term frequency and subword n-gram hashing so semantically overlapping texts yield high cosine similarity.
    """
    def __init__(self, dimensions: int = 128):
        self.dimensions = dimensions

    def _stem(self, word: str) -> str:
        for suffix in ("ing", "ed", "es", "s"):
            if len(word) > len(suffix) + 2 and word.endswith(suffix):
                return word[:-len(suffix)]
        return word

    def embed(self, text: str) -> list[float]:
        clean_text = text.lower().strip()
        tokens = re.findall(r'\b\w+\b', clean_text)
        if not tokens:
            return [0.0] * self.dimensions

        vec = [0.0] * self.dimensions
        for raw_token in tokens:
            token = self._stem(raw_token)
            idx = int(hashlib.md5(token.encode('utf-8')).hexdigest(), 16) % self.dimensions
            vec[idx] += 1.0

        # Subword character 3-grams for inflection and partial match tolerance
        for i in range(len(clean_text) - 2):
            trigram = clean_text[i:i+3]
            idx = int(hashlib.md5(trigram.encode('utf-8')).hexdigest(), 16) % self.dimensions
            vec[idx] += 0.15

        # Normalize to unit length (L2 norm)
        norm = math.sqrt(sum(v * v for v in vec))
        if norm > 0:
            vec = [v / norm for v in vec]

        return vec


class OllamaEmbeddingClient(BaseEmbeddingClient):
    """
    Zero-cost local embeddings powered by local Ollama instance
    (e.g., nomic-embed-text or all-minilm).
    """
    def __init__(self, model_name: str = "nomic-embed-text", host: str = "http://localhost:11434"):
        self.model_name = model_name
        self.host = host

    def embed(self, text: str) -> list[float]:
        try:
            response = requests.post(
                f"{self.host}/api/embeddings",
                json={
                    "model": self.model_name,
                    "prompt": text
                },
                timeout=60
            )
            response.raise_for_status()
            data = response.json()
            return data.get("embedding", [])
        except Exception as exc:
            raise RuntimeError(f"Ollama embedding failed for model '{self.model_name}': {exc}")


def create_embedding_client(provider_or_model: str = "auto") -> BaseEmbeddingClient:
    if provider_or_model.startswith("ollama:"):
        model = provider_or_model.split(":", 1)[1]
        return OllamaEmbeddingClient(model_name=model)
    elif provider_or_model == "ollama":
        return OllamaEmbeddingClient()
    return DeterministicEmbeddingClient()
