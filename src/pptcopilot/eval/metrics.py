"""Simple deterministic metrics for SPOCK-lite scenarios."""

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
