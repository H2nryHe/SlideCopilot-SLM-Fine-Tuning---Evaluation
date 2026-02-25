"""Citation helpers."""

from __future__ import annotations


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
