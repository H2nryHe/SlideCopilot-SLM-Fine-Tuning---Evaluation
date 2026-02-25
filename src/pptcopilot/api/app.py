"""Optional FastAPI app for production-style demo endpoints."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from pptcopilot.eval.harness import run_eval_suite
from pptcopilot.qa.answer import answer_question
from pptcopilot.summarize.baseline import summarize_jsonl

logger = logging.getLogger(__name__)


@dataclass
class SummarizeRequest:
    input_jsonl: str
    model: str = "mock"
    include_slide_bullets: bool = True


@dataclass
class QARequest:
    index_dir: str
    question: str
    top_k: int = 3
    debug: bool = False


@dataclass
class EvalRunRequest:
    suite: str = "smoke"
    models: list[str] | None = None
    outdir: str = "reports/eval"


def create_app():
    try:
        from fastapi import FastAPI, HTTPException
    except ImportError as exc:
        raise RuntimeError(
            "FastAPI is not installed. Install with: python -m pip install -e '.[api]'"
        ) from exc

    app = FastAPI(title="ppt-copilot API", version="0.1.0")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/summarize")
    def summarize(body: dict[str, object]) -> dict[str, object]:
        try:
            req = SummarizeRequest(
                input_jsonl=str(body["input_jsonl"]),
                model=str(body.get("model", "mock")),
                include_slide_bullets=bool(body.get("include_slide_bullets", True)),
            )
            return summarize_jsonl(
                req.input_jsonl,
                model=req.model,
                include_slide_bullets=req.include_slide_bullets,
            )
        except Exception as exc:
            logger.exception("API /summarize failed")
            raise HTTPException(status_code=400, detail=f"summarize failed: {exc}") from exc

    @app.post("/qa")
    def qa(body: dict[str, object]) -> dict[str, object]:
        try:
            req = QARequest(
                index_dir=str(body["index_dir"]),
                question=str(body["question"]),
                top_k=int(body.get("top_k", 3)),
                debug=bool(body.get("debug", False)),
            )
            return answer_question(
                index_dir=req.index_dir,
                question=req.question,
                top_k=req.top_k,
                debug=req.debug,
            )
        except Exception as exc:
            logger.exception("API /qa failed")
            raise HTTPException(status_code=400, detail=f"qa failed: {exc}") from exc

    @app.post("/eval/run")
    def eval_run(body: dict[str, object]) -> dict[str, object]:
        try:
            default_req = EvalRunRequest()
            req = EvalRunRequest(
                suite=str(body.get("suite", default_req.suite)),
                models=[str(x) for x in body.get("models", default_req.models or ["mock"])],
                outdir=str(body.get("outdir", default_req.outdir)),
            )
            return run_eval_suite(
                suite=req.suite,
                models=req.models or ["mock"],
                outdir=req.outdir,
            )
        except Exception as exc:
            logger.exception("API /eval/run failed")
            raise HTTPException(status_code=400, detail=f"eval run failed: {exc}") from exc

    return app


try:
    app = create_app()
except RuntimeError:
    async def app(scope, receive, send):  # type: ignore[no-redef]
        message = (
            "FastAPI dependency missing. Install with: "
            "python -m pip install -e '.[api]'"
        ).encode("utf-8")
        await send(
            {
                "type": "http.response.start",
                "status": 500,
                "headers": [(b"content-type", b"text/plain; charset=utf-8")],
            }
        )
        await send({"type": "http.response.body", "body": message})
