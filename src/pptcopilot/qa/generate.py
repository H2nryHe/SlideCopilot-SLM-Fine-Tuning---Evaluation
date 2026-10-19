"""Answer-generation backends for retrieval-grounded QA."""

from __future__ import annotations

from functools import lru_cache


def _context_block(hits: list[dict[str, object]], *, max_chunks: int = 3) -> str:
    """Build generation context without exposing citation IDs to the model."""
    lines: list[str] = []
    for rank, hit in enumerate(hits[:max_chunks], start=1):
        text = str(hit.get("chunk_text", ""))
        lines.append(f"Context item {rank}: {text}")
    return "\n".join(lines)


def extractive_answer(question: str, hits: list[dict[str, object]]) -> str:
    """Legacy deterministic answer used by unit tests and baseline runs."""
    del question
    if not hits:
        return "INSUFFICIENT_CONTEXT"
    snippets = [str(hit["chunk_text"]) for hit in hits[:2]]
    return "Based on retrieved slides: " + " | ".join(snippets)


@lru_cache(maxsize=2)
def _load_seq2seq_model(model_name: str):
    try:
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "Real generation requires transformers/torch. "
            "Install with: python -m pip install -e '.[rag]'"
        ) from exc

    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForSeq2SeqLM.from_pretrained(model_name)
    model.eval()
    return tokenizer, model


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
        "Return the requested value, name, metric, or short phrase directly. "
        "Do not output context labels and do not copy whole context items. "
        "If the context does not contain the answer, output exactly INSUFFICIENT_CONTEXT. "
        "Return only a concise answer, not an explanation.\n\n"
        f"Question: {question}\n\n"
        f"Context:\n{_context_block(hits)}"
    )
    tokenizer, model = _load_seq2seq_model(model_name)
    encoded = tokenizer(
        prompt,
        return_tensors="pt",
        truncation=True,
        max_length=512,
    )
    output_ids = model.generate(
        **encoded,
        max_new_tokens=max_new_tokens,
        do_sample=False,
        num_beams=1,
    )
    return str(tokenizer.decode(output_ids[0], skip_special_tokens=True)).strip()


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
