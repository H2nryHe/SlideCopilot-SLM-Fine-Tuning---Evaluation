"""Answer-generation backends for retrieval-grounded QA."""

from __future__ import annotations

from functools import lru_cache


def _context_block(hits: list[dict[str, object]], *, max_chunks: int = 5) -> str:
    lines: list[str] = []
    for hit in hits[:max_chunks]:
        slide_id = str(hit.get("slide_id", ""))
        text = str(hit.get("chunk_text", ""))
        lines.append(f"[{slide_id}] {text}")
    return "\n".join(lines)


def extractive_answer(question: str, hits: list[dict[str, object]]) -> str:
    """Legacy deterministic answer used by unit tests and baseline runs."""
    del question
    if not hits:
        return "INSUFFICIENT_CONTEXT"
    snippets = [str(hit["chunk_text"]) for hit in hits[:2]]
    return "Based on retrieved slides: " + " | ".join(snippets)


@lru_cache(maxsize=2)
def _load_text2text_pipeline(model_name: str):
    try:
        from transformers import pipeline  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "Real generation requires transformers/torch. "
            "Install with: python -m pip install -e '.[rag]'"
        ) from exc
    return pipeline("text2text-generation", model=model_name, tokenizer=model_name, device=-1)


def hf_answer(
    question: str,
    hits: list[dict[str, object]],
    *,
    model_name: str,
    max_new_tokens: int = 64,
) -> str:
    """Generate an answer with a real local Hugging Face seq2seq model."""
    if not hits:
        return "INSUFFICIENT_CONTEXT"

    prompt = (
        "Answer the question using only the context below. "
        "If the context does not contain the answer, output exactly INSUFFICIENT_CONTEXT. "
        "Return only a concise answer, not an explanation.\n\n"
        f"Question: {question}\n\n"
        f"Context:\n{_context_block(hits)}"
    )
    generator = _load_text2text_pipeline(model_name)
    result = generator(
        prompt,
        max_new_tokens=max_new_tokens,
        do_sample=False,
    )
    return str(result[0]["generated_text"]).strip()


def generate_answer(
    question: str,
    hits: list[dict[str, object]],
    *,
    backend: str,
    max_new_tokens: int = 64,
) -> str:
    if backend == "extractive":
        return extractive_answer(question, hits)
    if backend.startswith("hf:"):
        model_name = backend.split(":", 1)[1].strip()
        if not model_name:
            raise ValueError("HF generator must be specified as hf:<model_name>")
        return hf_answer(
            question,
            hits,
            model_name=model_name,
            max_new_tokens=max_new_tokens,
        )
    raise ValueError("Unsupported generator backend. Use 'extractive' or 'hf:<model_name>'.")
