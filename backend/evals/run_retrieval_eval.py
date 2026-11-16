"""Compare dense, BM25, and hybrid retrieval on manually labelled cases.

Run inside the backend Docker network so MYSQL_HOST=db and the vector store are
reachable:
    docker compose run --rm --no-deps backend python evals/run_retrieval_eval.py \
        --cases evals/retrieval_cases.jsonl
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import settings
from app.db.session import SessionLocal
from app.services.embeddig.embedding_factory import EmbeddingFactory
from app.services.hybrid_retriever import HybridRetriever, RetrievalStrategy
from app.services.vector_store.factory import VectorStoreFactory

VALID_STRATEGIES: tuple[RetrievalStrategy, ...] = ("dense", "bm25", "hybrid")


def load_cases(path: Path) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        case = json.loads(line)
        required = {"id", "knowledge_base_id", "query", "relevant_chunk_ids"}
        missing = required - case.keys()
        if missing or not isinstance(case["relevant_chunk_ids"], list):
            raise ValueError(f"Line {line_number} is not a valid retrieval case: missing {missing}")
        cases.append(case)
    if not cases:
        raise ValueError("The evaluation file contains no cases.")
    return cases


def reciprocal_rank(retrieved_ids: list[str], relevant_ids: set[str]) -> float:
    for rank, chunk_id in enumerate(retrieved_ids, start=1):
        if chunk_id in relevant_ids:
            return 1.0 / rank
    return 0.0


def evaluate(cases: list[dict[str, Any]], top_ks: list[int]) -> dict[str, dict[str, float]]:
    final_k = max(top_ks)
    embeddings = EmbeddingFactory.create()
    vector_stores: dict[int, Any] = {}
    report: dict[str, dict[str, float]] = {}

    with SessionLocal() as db:
        for strategy in VALID_STRATEGIES:
            hits = defaultdict(int)
            reciprocal_ranks: list[float] = []
            for case in cases:
                kb_id = int(case["knowledge_base_id"])
                vector_store = vector_stores.get(kb_id)
                if vector_store is None:
                    vector_store = VectorStoreFactory.create(
                        store_type=settings.VECTOR_STORE_TYPE,
                        collection_name=f"kb_{kb_id}",
                        embeddings_function=embeddings,
                    )
                    vector_stores[kb_id] = vector_store
                results = HybridRetriever(
                    vector_stores=[vector_store],
                    db=db,
                    knowledge_base_ids=[kb_id],
                    final_k=final_k,
                ).retrieve(case["query"], strategy=strategy)
                retrieved_ids = [str(item.metadata.get("chunk_id", "")) for item in results]
                relevant_ids = {str(chunk_id) for chunk_id in case["relevant_chunk_ids"]}
                for top_k in top_ks:
                    if relevant_ids.intersection(retrieved_ids[:top_k]):
                        hits[top_k] += 1
                reciprocal_ranks.append(reciprocal_rank(retrieved_ids, relevant_ids))

            total = len(cases)
            report[strategy] = {
                **{f"Recall@{top_k}": hits[top_k] / total for top_k in top_ks},
                "MRR": sum(reciprocal_ranks) / total,
            }
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate TraceRAG retrieval strategies.")
    parser.add_argument("--cases", type=Path, required=True, help="Path to a JSONL evaluation set.")
    parser.add_argument("--top-k", type=int, nargs="+", default=[1, 3, 5])
    args = parser.parse_args()
    if any(top_k < 1 for top_k in args.top_k):
        parser.error("--top-k values must be positive integers")

    report = evaluate(load_cases(args.cases), sorted(set(args.top_k)))
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
