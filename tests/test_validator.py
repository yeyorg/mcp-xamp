"""Unit tests for query validation, write gate, and database parameter check."""

import pytest

from mcp_xamp.security.validator import (
    check_write_allowed,
    require_database,
    validate_read_query,
)
from mcp_xamp.types import XampMissingDatabaseError, XampQueryError, XampWriteRejectedError

# ---------------------------------------------------------------------------
# validate_read_query
# ---------------------------------------------------------------------------


class TestValidateReadQuery:
    VALID_KEYWORDS = ["SELECT", "SHOW", "DESCRIBE", "EXPLAIN", "WITH"]

    @pytest.mark.parametrize("kw", VALID_KEYWORDS)
    def test_valid_keywords_pass(self, kw: str) -> None:
        validate_read_query(f"{kw} * FROM t")
        validate_read_query(f"{kw.lower()} * FROM t")
        validate_read_query(f"  {kw}  1+1  ")

    INVALID_KEYWORDS = [
        "INSERT",
        "UPDATE",
        "DELETE",
        "DROP",
        "ALTER",
        "CREATE",
        "TRUNCATE",
        "GRANT",
        "REVOKE",
    ]

    @pytest.mark.parametrize("kw", INVALID_KEYWORDS)
    def test_forbidden_keywords_rejected(self, kw: str) -> None:
        with pytest.raises(XampQueryError):
            validate_read_query(f"{kw} INTO t VALUES(1)")

    @pytest.mark.parametrize("kw", INVALID_KEYWORDS)
    def test_forbidden_keywords_rejected_case_insensitive(self, kw: str) -> None:
        with pytest.raises(XampQueryError):
            validate_read_query(f"{kw.lower()} something")
        with pytest.raises(XampQueryError):
            validate_read_query(f"  {kw.upper()}  ")

    def test_empty_query_raises(self) -> None:
        with pytest.raises(XampQueryError):
            validate_read_query("")
        with pytest.raises(XampQueryError):
            validate_read_query("   ")

    def test_none_query_raises(self) -> None:
        with pytest.raises(XampQueryError):
            validate_read_query(None)  # type: ignore[arg-type]

    def test_unknown_keyword_raises(self) -> None:
        with pytest.raises(XampQueryError):
            validate_read_query("FOOBAR something")

    def test_with_cte_accepted(self) -> None:
        validate_read_query("WITH cte AS (SELECT 1) SELECT * FROM cte")

    def test_placeholder_single_accepted(self) -> None:
        """A %s placeholder in a SELECT query must NOT trigger a validation error (AC3.4)."""
        validate_read_query("SELECT * FROM t WHERE c = %s")

    def test_placeholder_multiple_accepted(self) -> None:
        """%s placeholders in multi-condition queries must be accepted (AC3.4)."""
        validate_read_query("SELECT * FROM t WHERE a = %s AND b = %s")


# ---------------------------------------------------------------------------
# require_database
# ---------------------------------------------------------------------------


class TestRequireDatabase:
    def test_none_raises(self) -> None:
        with pytest.raises(XampMissingDatabaseError) as exc:
            require_database(None)
        assert "database" in str(exc.value).lower()
        assert "list_databases" in str(exc.value)

    def test_empty_string_raises(self) -> None:
        with pytest.raises(XampMissingDatabaseError):
            require_database("")

    def test_whitespace_only_raises(self) -> None:
        with pytest.raises(XampMissingDatabaseError):
            require_database("   ")

    def test_valid_name_passes(self) -> None:
        require_database("my_database")  # no exception


# ---------------------------------------------------------------------------
# check_write_allowed
# ---------------------------------------------------------------------------


class TestCheckWriteAllowed:
    def test_default_rejected(self, monkeypatch) -> None:
        monkeypatch.delenv("MCP_XAMP_ALLOW_WRITE", raising=False)
        with pytest.raises(XampWriteRejectedError) as exc:
            check_write_allowed()
        assert "MCP_XAMP_ALLOW_WRITE" in str(exc.value)

    def test_explicit_true_passes(self, monkeypatch) -> None:
        monkeypatch.setenv("MCP_XAMP_ALLOW_WRITE", "true")
        check_write_allowed()  # no exception

    def test_uppercase_true_passes(self, monkeypatch) -> None:
        monkeypatch.setenv("MCP_XAMP_ALLOW_WRITE", "TRUE")
        check_write_allowed()

    def test_false_rejected(self, monkeypatch) -> None:
        monkeypatch.setenv("MCP_XAMP_ALLOW_WRITE", "false")
        with pytest.raises(XampWriteRejectedError):
            check_write_allowed()

    def test_garbage_value_rejected(self, monkeypatch) -> None:
        monkeypatch.setenv("MCP_XAMP_ALLOW_WRITE", "yes")
        with pytest.raises(XampWriteRejectedError):
            check_write_allowed()
