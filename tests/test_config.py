from pathlib import Path

from pptcopilot.config import get_paths


def test_get_paths_defaults_under_repo() -> None:
    paths = get_paths()
    assert (paths.repo_root / "pyproject.toml").exists()
    assert paths.data_dir == paths.repo_root / "data"
    assert paths.reports_dir == paths.repo_root / "reports"


def test_get_paths_with_custom_root() -> None:
    root = Path("/tmp/demo-root")
    paths = get_paths(root)
    assert paths.repo_root == root
