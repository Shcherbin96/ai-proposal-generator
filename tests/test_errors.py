from proposal_gen.errors import ConfigError, InputError, LLMError, ProposalError, RenderError


def test_error_hierarchy_and_exit_codes():
    assert issubclass(InputError, ProposalError)
    assert issubclass(ConfigError, ProposalError)
    assert issubclass(LLMError, ProposalError)
    assert issubclass(RenderError, ProposalError)
    assert InputError.exit_code == 65  # EX_DATAERR
    assert ConfigError.exit_code == 78  # EX_CONFIG
    assert LLMError.exit_code == 69  # EX_UNAVAILABLE
    assert RenderError.exit_code == 73  # EX_CANTCREAT
