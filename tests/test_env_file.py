"""The .env loader must accept the inline comments used in .env.example."""

from __future__ import annotations

import os

from contexto_solver.config import _strip_inline_comment, load_dotenv


def test_inline_comments_are_dropped(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "TEST_URL=http://localhost:11434/v1      # must end in /v1\n"
        "TEST_MODEL=qwen3:14b                     # study models\n"
        "TEST_SELECTION=mu_plus_lambda   # mu_plus_lambda | random\n"
        'TEST_QUOTED="value with # inside"\n'
        "TEST_HASH=abc#def\n"
        "# a comment line\n"
        "TEST_EMPTY=\n",
        encoding="utf-8",
    )
    for key in ("TEST_URL", "TEST_MODEL", "TEST_SELECTION", "TEST_QUOTED", "TEST_HASH", "TEST_EMPTY"):
        monkeypatch.delenv(key, raising=False)
    load_dotenv(env_file)
    assert os.environ["TEST_URL"] == "http://localhost:11434/v1"
    assert os.environ["TEST_MODEL"] == "qwen3:14b"
    assert os.environ["TEST_SELECTION"] == "mu_plus_lambda"
    assert os.environ["TEST_HASH"] == "abc#def"  # no whitespace before '#': not a comment
    assert os.environ["TEST_EMPTY"] == ""
    assert _strip_inline_comment('"quoted"  # note') == "quoted"


def test_example_env_file_parses_cleanly(tmp_path, monkeypatch):
    from pathlib import Path

    example = Path(__file__).resolve().parents[1] / ".env.example"
    values = {}
    for line in example.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = _strip_inline_comment(value)
    assert values["OLLAMA_BASE_URL"] == "http://localhost:11434/v1"
    assert values["OLLAMA_MODEL"] == "qwen3:14b"
    assert values["SELECTION"] == "mu_plus_lambda"
    assert values["RATIONALE_CHANNEL"] == "inherited"
    assert values["SELF_REPORT"] == "1"
