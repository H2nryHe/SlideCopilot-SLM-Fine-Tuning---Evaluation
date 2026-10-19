"""Deterministic evaluation metrics for SlideCopilot."""

from __future__ import annotations

import re


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def keyword_coverage(text: str, required_points: list[str]) -> dict[str, object]:
    normalized = _normalize(text)
    if not required_points:
        return {"covered": 0, "total": 0, "coverage": 1.0, "missing": []}
    covered_points = [p for p in required_points if _normalize(p) in normalized]
    missing_points = [p for p in required_points if p not in covered_points]
    coverage = len(covered_points) / len(required_points)
    return {
        "covered": len(covered_points),
        "total": len(required_points),
        "coverage": round(coverage, 4),
        "missing": missing_points,
    }


def answer_match(answer: str, acceptable_answers: list[str]) -> dict[str, object]:
    normalized = _normalize(answer)
    if not acceptable_answers:
        return {"matched": True, "matched_answer": None}
    for candidate in acceptable_answers:
        if _normalize(candidate) in normalized:
            return {"matched": True, "matched_answer": candidate}
    return {"matched": False, "matched_answer": None}


def citation_recall(
    cited_slide_ids: list[str],
    expected_slide_ids: list[str],
) -> dict[str, object]:
    cited = list(dict.fromkeys(cited_slide_ids))
    expected = list(dict.fromkeys(expected_slide_ids))
    if not expected:
        return {"matched": 0, "total_expected": 0, "recall": 1.0, "missing": []}
    matched = [s for s in expected if s in cited]
    missing = [s for s in expected if s not in cited]
    recall = len(matched) / len(expected)
    return {
        "matched": len(matched),
        "total_expected": len(expected),
        "recall": round(recall, 4),
        "missing": missing,
    }


def _unique_ranked_slide_ids(slide_ids: list[str]) -> list[str]:
    return list(dict.fromkeys(slide_ids))


def retrieval_recall_at_k(
    ranked_slide_ids: list[str],
    expected_slide_ids: list[str],
    *,
    k: int,
) -> float:
    if k <= 0:
        raise ValueError("k must be positive")
    expected = set(expected_slide_ids)
    if not expected:
        return 1.0
    ranked = _unique_ranked_slide_ids(ranked_slide_ids)[:k]
    return len(expected.intersection(ranked)) / len(expected)


def reciprocal_rank(
    ranked_slide_ids: list[str],
    expected_slide_ids: list[str],
) -> float:
    expected = set(expected_slide_ids)
    if not expected:
        return 1.0
    for rank, slide_id in enumerate(_unique_ranked_slide_ids(ranked_slide_ids), start=1):
        if slide_id in expected:
            return 1.0 / rank
    return 0.0
