"""Kept out of webapp/intake.py so that the API contract can import it without loading the job store
(test_the_contract_imports_without_flask_or_the_store)."""
from typing import Literal

IntakeRefusalCode = Literal[
    "no_statements", "too_many_statements", "invalid_filename", "statement_too_large", "not_a_pdf", "pdf_encrypted",
    "pdf_unreadable", "too_many_pages", "storage_full", "not_stored",
]
