from pptcopilot.cli import build_parser, main


def test_help_contains_program_name() -> None:
    parser = build_parser()
    help_text = parser.format_help()
    assert "pptcopilot" in help_text


def test_main_hello_runs() -> None:
    exit_code = main(["hello"])
    assert exit_code == 0


def test_help_contains_summarize_command() -> None:
    parser = build_parser()
    help_text = parser.format_help()
    assert "summarize" in help_text


def test_help_contains_retrieval_commands() -> None:
    parser = build_parser()
    help_text = parser.format_help()
    assert "index" in help_text
    assert "qa" in help_text


def test_help_contains_eval_command() -> None:
    parser = build_parser()
    help_text = parser.format_help()
    assert "eval" in help_text


def test_help_contains_finetune_command() -> None:
    parser = build_parser()
    help_text = parser.format_help()
    assert "finetune" in help_text


def test_help_contains_bench_command() -> None:
    parser = build_parser()
    help_text = parser.format_help()
    assert "bench" in help_text
