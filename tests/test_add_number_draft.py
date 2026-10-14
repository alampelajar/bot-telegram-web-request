import pytest

from app.services.add_number_draft import (
    AddNumberDraftError,
    MAX_DRAFT_COUNT,
    parse_add_number_draft,
)


def test_parse_valid_add_number_draft() -> None:
    draft = parse_add_number_draft("term_123 term-456 5 asc")
    assert draft.termination_id == "term_123"
    assert draft.termination_term_id == "term-456"
    assert draft.count == 5
    assert draft.sort_type == "asc"


@pytest.mark.parametrize(
    "arguments",
    [
        "",
        "term_123 term_456 5",
        "term_123 term_456 5 asc extra",
        "term/123 term_456 5 asc",
        "term_123 term_456 0 asc",
        f"term_123 term_456 {MAX_DRAFT_COUNT + 1} asc",
        "term_123 term_456 five asc",
        "term_123 term_456 5 asc;DROP",
    ],
)
def test_invalid_add_number_draft_is_rejected(arguments: str) -> None:
    with pytest.raises(AddNumberDraftError):
        parse_add_number_draft(arguments)


def test_summary_does_not_include_tokens_or_password_fields() -> None:
    draft = parse_add_number_draft("term_123 term_456 2 asc")
    summary = draft.safe_summary().lower()
    assert "_token" not in summary
    assert "password" not in summary
    assert "cookie" not in summary
