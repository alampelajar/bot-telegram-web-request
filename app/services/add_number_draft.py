"""Validate Add Number business inputs without performing a website request.

The form field names are based on an observed browser request. CSRF/request tokens
are deliberately excluded; this module only prepares a local draft.
"""
from dataclasses import dataclass
import re


_IDENTIFIER_RE = re.compile(r"^[0-9]{1,20}$")
_SORT_TYPE_RE = re.compile(r"^[A-Za-z0-9_-]{1,32}$")
MAX_DRAFT_COUNT = 1000


class AddNumberDraftError(ValueError):
    """The supplied Add Number draft parameters are invalid."""


@dataclass(frozen=True)
class AddNumberDraft:
    termination_id: str
    termination_term_id: str
    count: int
    sort_type: str

    def safe_summary(self) -> str:
        return (
            f"termination_id={self.termination_id}, "
            f"termination_term_id={self.termination_term_id}, "
            f"count={self.count}, sort_type={self.sort_type}"
        )


def parse_add_number_draft(arguments: str) -> AddNumberDraft:
    """Parse: <termination_id> <termination_term_id> <count> <sort_type>.

    The upper bound is a conservative local draft limit, not a claim about
    Augestel's own account or API limits.
    """
    parts = arguments.split()
    if len(parts) != 4:
        raise AddNumberDraftError(
            "Format: /addnumber <termination_id> <termination_term_id> <count> <sort_type>"
        )

    termination_id, termination_term_id, count_text, sort_type = parts
    if not _IDENTIFIER_RE.fullmatch(termination_id):
        raise AddNumberDraftError("termination_id harus berupa ID numerik Augestel.")
    if not _IDENTIFIER_RE.fullmatch(termination_term_id):
        raise AddNumberDraftError(
            "termination_term_id harus berupa ID numerik Augestel."
        )
    if not _SORT_TYPE_RE.fullmatch(sort_type):
        raise AddNumberDraftError("sort_type hanya boleh berisi huruf, angka, '_' atau '-'.")
    try:
        count = int(count_text, 10)
    except ValueError as exc:
        raise AddNumberDraftError("count harus berupa bilangan bulat.") from exc
    if not 1 <= count <= MAX_DRAFT_COUNT:
        raise AddNumberDraftError(f"count harus berada pada rentang 1–{MAX_DRAFT_COUNT}.")

    return AddNumberDraft(
        termination_id=termination_id,
        termination_term_id=termination_term_id,
        count=count,
        sort_type=sort_type,
    )
