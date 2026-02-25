from pptcopilot.api.app import app


def test_api_app_symbol_exists() -> None:
    # If FastAPI is unavailable, app is a fallback ASGI callable with guidance.
    assert callable(app)
