"""Citation helpers for attributing generated answers to retrieved slides."""

from __future__ import annotations

import re


TOKEN_RE = re.compile(r"[A-Za-z0-9_.%$@-]+")
STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "based", "be", "below", "by", "for",
    "from", "in", "is", "it", "of", "on", "or", "slide", "slides", "the", "this",
    "to", "was", "were", "with",
}


def unique_slide_citations(hits: list[dict[str, object]]) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for hit in hits:
        slide_id = str(hit.get("slide_id", "")).strip()
        if not slide_id or slide_id in seen:
            continue
        seen.add(slide_id)
        ordered.append(slide_id)
    return ordered


def _tokens(text: str) -> set[str]:
    return {
        token.lower()
        for token in TOKEN_RE.findall(text)
        if token.lower() not in STOPWORDS and len(token) > 1
    }


def select_answer_citations(
    answer: str,
    hits: list[dict[str, object]],
    *,
    max_citations: int = 2,
) -> list[str]:
    """Attribute an answer to the retrieved slide text that best supports it.

    This keeps citation evaluation independent from retrieval Recall@K: a slide is
    cited only when its content overlaps the final answer, rather than citing every
    retrieved item automatically.
    """
    if not hits or answer.strip() == "INSUFFICIENT_CONTEXT":
        return []

    answer_tokens = _tokens(answer)
    if not answer_tokens:
        return []

    per_slide: dict[str, float] = {}
    slide_rank: dict[str, int] = {}
    for rank, hit in enumerate(hits, start=1):
        slide_id = str(hit.get("slide_id", "")).strip()
        if not slide_id:
            continue
        support_tokens = _tokens(str(hit.get("chunk_text", "")))
        overlap = len(answer_tokens.intersection(support_tokens))
        score = overlap / max(1, len(answer_tokens))
        if score > per_slide.get(slide_id, 0.0):
            per_slide[slide_id] = score
        slide_rank.setdefault(slide_id, rank)

    ranked = sorted(
        (
            (slide_id, score)
            for slide_id, score in per_slide.items()
            if score > 0.0
        ),
        key=lambda item: (-item[1], slide_rank[item[0]]),
    )
    return [slide_id for slide_id, _ in ranked[:max_citations]]
