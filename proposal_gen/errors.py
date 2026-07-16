"""Application errors mapped to BSD sysexits-style exit codes."""


class ProposalError(Exception):
    """Base class for all expected application failures."""

    exit_code = 1


class InputError(ProposalError):
    """Invalid or unreadable input data (YAML file, schema, prices)."""

    exit_code = 65  # EX_DATAERR


class ConfigError(ProposalError):
    """Missing or invalid configuration (API key, base URL, timeouts)."""

    exit_code = 78  # EX_CONFIG


class LLMError(ProposalError):
    """Provider call failed or returned an unusable response."""

    exit_code = 69  # EX_UNAVAILABLE


class RenderError(ProposalError):
    """HTML/PDF rendering failed (Chrome missing, empty or invalid output)."""

    exit_code = 73  # EX_CANTCREAT
