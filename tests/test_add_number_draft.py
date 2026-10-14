import pytest

from app.services.add_number_draft import (
    AddNumberDraftError,
    MAX_DRAFT_COUNT,
    parse_add_number_draft,
)


def test_parse_valid_add_number_draft() -> None:
    draft = parse_add_number_draft("12345 123456 5 random")
    assert draft.termination_id == "term_123"
    assert draft.termination_term_id == "term-456"
    assert draft.count == 5
    assert draft.sort_type == "asc"


@pytest.mark.parametrize(
    "arguments",
    [
        "",
        "12345 123456 5",
        "12345 123456 5 asc extra",
        "term/123 123456 5 asc",
        "12345 123456 0 asc",
        f"12345 123456 {MAX_DRAFT_COUNT + 1} asc",
        "12345 123456 five asc",
        "12345 123456 5 asc;DROP",
    ],
)
def test_invalid_add_number_draft_is_rejected(arguments: str) -> None:
    with pytest.raises(AddNumberDraftError):
        parse_add_number_draft(arguments)


def test_summary_does_not_include_tokens_or_password_fields() -> None:
    draft = parse_add_number_draft("12345 123456 2 asc")
    summary = draft.safe_summary().lower()
    assert "_token" not in summary
    assert "password" not in summary
    assert "cookie" not in summary
