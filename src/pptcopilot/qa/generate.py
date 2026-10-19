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


def _evidence_block(hits: list[dict[str, object]], *, max_chunks: int = 5) -> str:
    return "\n".join(
        f"<evidence>{str(hit.get('chunk_text', ''))}</evidence>"
        for hit in hits[:max_chunks]
    )


SPAN_EXTRACTION_INSTRUCTION = (
    "Copy the shortest exact text span from the evidence that directly answers the "
    "question. Do not infer, calculate, paraphrase, or output evidence IDs. Preserve "
    "numeric units and qualifiers, and preserve complete proper names, standards, and "
    "lists. Output only the answer span. If the answer is absent, output exactly "
    "INSUFFICIENT_CONTEXT."
)


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


@lru_cache(maxsize=1)
def _load_causal_model(model_name: str):
    try:
        from transformers import AutoModelForCausalLM, AutoTokenizer  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "Real generation requires transformers/torch. "
            "Install with: python -m pip install -e '.[rag]'"
        ) from exc

    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForCausalLM.from_pretrained(model_name)
    model.eval()
    return tokenizer, model


@lru_cache(maxsize=1)
def _load_qa_model(model_name: str):
    try:
        from transformers import AutoModelForQuestionAnswering, AutoTokenizer  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "Real generation requires transformers/torch. "
            "Install with: python -m pip install -e '.[rag]'"
        ) from exc

    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForQuestionAnswering.from_pretrained(model_name)
    model.eval()
    return tokenizer, model


def get_hf_model_metadata(
    model_name: str, *, causal: bool = False, question_answering: bool = False
) -> dict[str, object]:
    """Return the resolved model identity recorded with benchmark artifacts."""
    if causal:
        tokenizer, model = _load_causal_model(model_name)
    elif question_answering:
        tokenizer, model = _load_qa_model(model_name)
    else:
        tokenizer, model = _load_seq2seq_model(model_name)
    try:
        import transformers  # type: ignore

        transformers_version = str(transformers.__version__)
    except ImportError:  # pragma: no cover - model loading already raises first
        transformers_version = "unknown"
    revision = getattr(model.config, "_commit_hash", None)
    if not revision:
        revision = getattr(tokenizer, "init_kwargs", {}).get("_commit_hash")
    parameter_count = sum(parameter.numel() for parameter in model.parameters())
    return {
        "requested_name": model_name,
        "resolved_name_or_path": str(getattr(model.config, "_name_or_path", model_name)),
        "revision": revision,
        "architecture": model.__class__.__name__,
        "parameter_count": int(parameter_count),
        "transformers_version": transformers_version,
    }


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


def hf_span_answer(
    question: str,
    hits: list[dict[str, object]],
    *,
    model_name: str,
    max_new_tokens: int = 64,
) -> str:
    """Extract an answer span with a local seq2seq model and an explicit contract."""
    if not hits:
        return "INSUFFICIENT_CONTEXT"
    prompt = (
        f"{SPAN_EXTRACTION_INSTRUCTION}\n\n"
        f"Question: {question}\n\n"
        f"Evidence:\n{_evidence_block(hits)}\n\nAnswer:"
    )
    tokenizer, model = _load_seq2seq_model(model_name)
    encoded = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=512)
    output_ids = model.generate(
        **encoded,
        max_new_tokens=max_new_tokens,
        do_sample=False,
        num_beams=1,
    )
    return str(tokenizer.decode(output_ids[0], skip_special_tokens=True)).strip()


def hf_causal_answer(
    question: str,
    hits: list[dict[str, object]],
    *,
    model_name: str,
    max_new_tokens: int = 64,
) -> str:
    """Generate an answer with a local instruction-tuned causal model."""
    if not hits:
        return "INSUFFICIENT_CONTEXT"

    tokenizer, model = _load_causal_model(model_name)
    messages = [
        {
            "role": "system",
            "content": (
                "Answer questions using only the supplied context. If the answer is "
                "absent, reply exactly INSUFFICIENT_CONTEXT. Return only the shortest "
                "complete answer and preserve units and metric names from the context."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Context:\n{_context_block(hits)}\n\n"
                f"Question: {question}\n\nAnswer:"
            ),
        },
    ]
    if hasattr(tokenizer, "apply_chat_template") and tokenizer.chat_template:
        prompt = tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )
    else:
        prompt = "\n\n".join(message["content"] for message in messages)
    encoded = tokenizer(
        prompt,
        return_tensors="pt",
        truncation=True,
        max_length=1024,
    )
    output_ids = model.generate(
        **encoded,
        max_new_tokens=max_new_tokens,
        do_sample=False,
        pad_token_id=tokenizer.eos_token_id,
    )
    generated_ids = output_ids[0, encoded["input_ids"].shape[1] :]
    return str(tokenizer.decode(generated_ids, skip_special_tokens=True)).strip()


def hf_causal_span_answer(
    question: str,
    hits: list[dict[str, object]],
    *,
    model_name: str,
    max_new_tokens: int = 64,
) -> str:
    """Extract an answer span with an instruction-tuned causal model."""
    if not hits:
        return "INSUFFICIENT_CONTEXT"

    tokenizer, model = _load_causal_model(model_name)
    messages = [
        {"role": "system", "content": SPAN_EXTRACTION_INSTRUCTION},
        {
            "role": "user",
            "content": (
                f"Evidence:\n{_evidence_block(hits)}\n\n"
                f"Question: {question}\n\nAnswer:"
            ),
        },
    ]
    if hasattr(tokenizer, "apply_chat_template") and tokenizer.chat_template:
        prompt = tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )
    else:
        prompt = "\n\n".join(message["content"] for message in messages)
    encoded = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=1024)
    output_ids = model.generate(
        **encoded,
        max_new_tokens=max_new_tokens,
        do_sample=False,
        pad_token_id=tokenizer.eos_token_id,
    )
    generated_ids = output_ids[0, encoded["input_ids"].shape[1] :]
    return str(tokenizer.decode(generated_ids, skip_special_tokens=True)).strip()


def hf_qa_answer(
    question: str,
    hits: list[dict[str, object]],
    *,
    model_name: str,
    max_answer_tokens: int = 32,
) -> str:
    """Extract the highest-scoring answer span with a local QA model."""
    if not hits:
        return "INSUFFICIENT_CONTEXT"

    context = "\n".join(str(hit.get("chunk_text", "")) for hit in hits[:5])
    tokenizer, model = _load_qa_model(model_name)
    encoded = tokenizer(
        question,
        context,
        return_tensors="pt",
        truncation="only_second",
        max_length=512,
    )
    model_inputs = {key: value for key, value in encoded.items() if key != "token_type_ids"}
    if "token_type_ids" in encoded:
        model_inputs["token_type_ids"] = encoded["token_type_ids"]
    outputs = model(**model_inputs)
    sequence_ids = encoded.sequence_ids(0)
    context_indices = [index for index, sequence_id in enumerate(sequence_ids) if sequence_id == 1]
    if not context_indices:
        return "INSUFFICIENT_CONTEXT"

    start_logits = outputs.start_logits[0]
    end_logits = outputs.end_logits[0]
    best_score: float | None = None
    best_span: tuple[int, int] | None = None
    context_index_set = set(context_indices)
    for start in context_indices:
        max_end = min(start + max_answer_tokens, context_indices[-1])
        for end in range(start, max_end + 1):
            if end not in context_index_set:
                continue
            score = float(start_logits[start] + end_logits[end])
            if best_score is None or score > best_score:
                best_score = score
                best_span = (start, end)
    if best_span is None:
        return "INSUFFICIENT_CONTEXT"
    token_ids = encoded["input_ids"][0, best_span[0] : best_span[1] + 1]
    return str(tokenizer.decode(token_ids, skip_special_tokens=True)).strip()


def generate_answer(
    question: str,
    hits: list[dict[str, object]],
    *,
    backend: str,
    max_new_tokens: int = 64,
) -> str:
    if backend == "extractive":
        return extractive_answer(question, hits)
    if backend.startswith("hf-qa:"):
        model_name = backend.split(":", 1)[1].strip()
        if not model_name:
            raise ValueError("HF QA generator must be specified as hf-qa:<model_name>")
        return hf_qa_answer(question, hits, model_name=model_name)
    if backend.startswith("hf-span:"):
        model_name = backend.split(":", 1)[1].strip()
        if not model_name:
            raise ValueError("HF span generator must be specified as hf-span:<model_name>")
        return hf_span_answer(
            question,
            hits,
            model_name=model_name,
            max_new_tokens=max_new_tokens,
        )
    if backend.startswith("hf-causal-span:"):
        model_name = backend.split(":", 1)[1].strip()
        if not model_name:
            raise ValueError(
                "HF causal span generator must be specified as "
                "hf-causal-span:<model_name>"
            )
        return hf_causal_span_answer(
            question,
            hits,
            model_name=model_name,
            max_new_tokens=max_new_tokens,
        )
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
    if backend.startswith("hf-causal:"):
        model_name = backend.split(":", 1)[1].strip()
        if not model_name:
            raise ValueError("HF causal generator must be specified as hf-causal:<model_name>")
        return hf_causal_answer(
            question,
            hits,
            model_name=model_name,
            max_new_tokens=max_new_tokens,
        )
    raise ValueError(
        "Unsupported generator backend. Use 'extractive', 'hf:<model_name>', "
        "'hf-qa:<model_name>', 'hf-span:<model_name>', 'hf-causal:<model_name>', or "
        "'hf-causal-span:<model_name>'."
    )
