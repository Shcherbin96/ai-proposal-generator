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
