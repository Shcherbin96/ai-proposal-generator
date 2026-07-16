import os
import subprocess
import sys
from pathlib import Path

import pytest

from proposal_gen.cli import main


def test_missing_api_key_exits_78(monkeypatch, capsys):
    monkeypatch.setenv("LLM_API_KEY", "")
    assert main(["data/products.yaml"]) == 78
    assert "LLM_API_KEY" in capsys.readouterr().err


def test_missing_input_file_exits_65(monkeypatch, capsys):
    monkeypatch.setenv("LLM_API_KEY", "test")
    assert main(["definitely-missing.yaml"]) == 65
    err = capsys.readouterr().err
    assert "Error:" in err and "not found" in err


def test_llm_failure_exits_69(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("LLM_API_KEY", "test")
    yaml_path = tmp_path / "p.yaml"
    yaml_path.write_text("client: c\nproject: p\nproducts: [{name: n, price: 1}]\n")

    from proposal_gen import cli

    class BrokenProvider:
        def complete(self, prompt: str) -> str:
            return "not json at all"

    monkeypatch.setattr(cli, "OpenAICompatProvider", lambda settings: BrokenProvider())
    assert main([str(yaml_path)]) == 69
    assert "JSON" in capsys.readouterr().err


def test_success_prints_path_and_exits_0(monkeypatch, tmp_path, capsys, canned_response):
    monkeypatch.setenv("LLM_API_KEY", "test")
    from proposal_gen import cli
    from proposal_gen.errors import RenderError
    from proposal_gen.render import find_chrome
    from tests.conftest import FakeProvider

    try:
        find_chrome()
    except RenderError:
        pytest.skip("Chrome/Chromium not installed")

    monkeypatch.setattr(cli, "OpenAICompatProvider", lambda settings: FakeProvider(canned_response))
    out = tmp_path / "kp.pdf"
    code = main(["data/products.yaml", "--output", str(out)])
    assert code == 0
    assert str(out) in capsys.readouterr().out
    assert out.is_file()


def test_render_failure_exits_73(monkeypatch, tmp_path, capsys, canned_response):
    monkeypatch.setenv("LLM_API_KEY", "test")
    # sys.executable exists everywhere and exits nonzero when fed Chrome's
    # flags: a portable "chrome that fails" (no /bin/false on macOS).
    monkeypatch.setenv("CHROME_PATH", sys.executable)
    from proposal_gen import cli
    from tests.conftest import FakeProvider

    monkeypatch.setattr(cli, "OpenAICompatProvider", lambda settings: FakeProvider(canned_response))
    code = main(["data/products.yaml", "--output", str(tmp_path / "x.pdf")])
    assert code == 73
    assert "Error:" in capsys.readouterr().err


def test_old_generate_module_entry_point_still_works(tmp_path):
    """python -m proposal_gen.generate was the originally documented command;
    it must behave like the CLI, not silently no-op."""
    env = {**os.environ, "LLM_API_KEY": ""}
    result = subprocess.run(
        [sys.executable, "-m", "proposal_gen.generate"],
        capture_output=True,
        encoding="utf-8",
        env=env,
        cwd=Path(__file__).parents[1],
    )
    assert result.returncode == 78  # ConfigError, same as python -m proposal_gen
    assert "LLM_API_KEY" in result.stderr
