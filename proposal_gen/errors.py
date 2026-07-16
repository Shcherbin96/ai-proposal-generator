"""Domain-specific exceptions exposed by the proposal generator."""


class ProposalGeneratorError(Exception):
    """Base class for expected, user-actionable failures."""

    error_type = "proposal_generator_error"


class ConfigurationError(ProposalGeneratorError):
    """Raised when required local configuration is missing or invalid."""

    error_type = "configuration_error"


class InputValidationError(ProposalGeneratorError):
    """Raised when the input YAML does not match the expected contract."""

    error_type = "input_validation_error"


class LLMResponseError(ProposalGeneratorError):
    """Raised when the provider request or structured response is invalid."""

    error_type = "llm_response_error"


class PDFRenderError(ProposalGeneratorError):
    """Raised when a browser cannot produce the PDF artifact."""

    error_type = "pdf_render_error"
