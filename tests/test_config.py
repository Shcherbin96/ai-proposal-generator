import pytest

from proposal_gen.config import DEFAULT_BASE_URL, DEFAULT_MODEL, load_settings
from proposal_gen.errors import ConfigError


def test_missing_key_raises_config_error(monkeypatch):
    # setenv to "" (not delenv): load_dotenv(override=False) must not resurrect
    # a developer's real .env key during tests.
    monkeypatch.setenv("LLM_API_KEY", "")
    with pytest.raises(ConfigError, match="LLM_API_KEY"):
        load_settings()


def test_defaults(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.delenv("LLM_TIMEOUT_S", raising=False)
    monkeypatch.delenv("LLM_MAX_RETRIES", raising=False)
    monkeypatch.delenv("LLM_TEMPERATURE", raising=False)
    s = load_settings()
    assert s.api_key == "test-key"
    assert s.base_url == DEFAULT_BASE_URL
    assert s.model == DEFAULT_MODEL
    assert s.timeout_s > 0 and s.max_retries >= 0
    assert s.temperature == 0.4


def test_overrides(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "k")
    monkeypatch.setenv("LLM_BASE_URL", "https://api.openai.com/v1")
    monkeypatch.setenv("LLM_MODEL", "gpt-4o-mini")
    monkeypatch.setenv("LLM_TIMEOUT_S", "10")
    monkeypatch.setenv("LLM_MAX_RETRIES", "0")
    monkeypatch.setenv("LLM_TEMPERATURE", "0.9")
    s = load_settings()
    assert s.base_url == "https://api.openai.com/v1"
    assert s.model == "gpt-4o-mini"
    assert s.timeout_s == 10.0
    assert s.max_retries == 0
    assert s.temperature == 0.9


def test_invalid_temperature_raises_config_error(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "k")
    monkeypatch.setenv("LLM_TEMPERATURE", "hot")
    with pytest.raises(ConfigError, match="LLM_TEMPERATURE"):
        load_settings()


@pytest.mark.parametrize("value", ["-1", "2.5"])
def test_out_of_range_temperature_raises_config_error(monkeypatch, value):
    monkeypatch.setenv("LLM_API_KEY", "k")
    monkeypatch.setenv("LLM_TEMPERATURE", value)
    with pytest.raises(ConfigError, match="LLM_TEMPERATURE"):
        load_settings()


def test_zero_temperature_is_valid(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "k")
    monkeypatch.setenv("LLM_TEMPERATURE", "0")
    s = load_settings()
    assert s.temperature == 0.0


def test_json_mode_defaults_true(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "k")
    monkeypatch.delenv("LLM_JSON_MODE", raising=False)
    assert load_settings().json_mode is True


@pytest.mark.parametrize("value", ["1", "true", "True", "TRUE", "yes", "on"])
def test_json_mode_truthy_values(monkeypatch, value):
    monkeypatch.setenv("LLM_API_KEY", "k")
    monkeypatch.setenv("LLM_JSON_MODE", value)
    assert load_settings().json_mode is True


@pytest.mark.parametrize("value", ["0", "false", "False", "FALSE", "no", "off"])
def test_json_mode_falsy_values(monkeypatch, value):
    monkeypatch.setenv("LLM_API_KEY", "k")
    monkeypatch.setenv("LLM_JSON_MODE", value)
    assert load_settings().json_mode is False


def test_json_mode_garbage_raises_config_error(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "k")
    monkeypatch.setenv("LLM_JSON_MODE", "maybe")
    with pytest.raises(ConfigError, match="LLM_JSON_MODE"):
        load_settings()


def test_invalid_numeric_settings_raise_config_error(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "k")
    monkeypatch.setenv("LLM_TIMEOUT_S", "soon")
    with pytest.raises(ConfigError, match="LLM_TIMEOUT_S"):
        load_settings()


@pytest.mark.parametrize("value", ["-5", "0"])
def test_non_positive_timeout_raises_config_error(monkeypatch, value):
    monkeypatch.setenv("LLM_API_KEY", "k")
    monkeypatch.setenv("LLM_TIMEOUT_S", value)
    with pytest.raises(ConfigError, match="LLM_TIMEOUT_S"):
        load_settings()


def test_negative_max_retries_raises_config_error(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "k")
    monkeypatch.setenv("LLM_MAX_RETRIES", "-1")
    with pytest.raises(ConfigError, match="LLM_MAX_RETRIES"):
        load_settings()


def test_empty_string_base_url_and_model_fall_back_to_defaults(monkeypatch):
    # getenv defaults only apply when a variable is UNSET; an empty string
    # (e.g. `LLM_BASE_URL=` in .env) must fall back to defaults too.
    monkeypatch.setenv("LLM_API_KEY", "k")
    monkeypatch.setenv("LLM_BASE_URL", "")
    monkeypatch.setenv("LLM_MODEL", "")
    s = load_settings()
    assert s.base_url == DEFAULT_BASE_URL
    assert s.model == DEFAULT_MODEL


def test_api_key_is_not_exposed_in_repr(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "sk-VERYSECRET")
    assert "VERYSECRET" not in repr(load_settings())
