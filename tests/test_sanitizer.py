"""Unit tests for error message sanitization."""

from mcp_xamp.security.sanitizer import sanitize_error


class TestSanitizeError:
    def test_strips_host_in_connection_error(self) -> None:
        msg = (
            "(2003, \"Can't connect to MySQL server on "
            "'db.example.com' ([Errno 11001] getaddrinfo failed)\")"
        )
        result = sanitize_error(msg)
        assert "db.example.com" not in result
        assert "***" in result

    def test_strips_user_in_auth_error(self) -> None:
        msg = "(1045, \"Access denied for user 'root'@'localhost' (using password: YES)\")"
        result = sanitize_error(msg)
        assert "root" not in result.lower() or "'***'@'***'" in result
        assert "password: ***" in result

    def test_strips_ip_address(self) -> None:
        msg = "Connection to 192.168.1.100:3306 timed out"
        result = sanitize_error(msg)
        assert "192.168.1.100" not in result

    def test_strips_port_number(self) -> None:
        msg = "failed connecting to server on port 3307"
        result = sanitize_error(msg)
        assert "3307" not in result

    def test_keeps_sql_error_code(self) -> None:
        msg = "(1064, \"You have an error in your SQL syntax near 'SELEC' at line 1\")"
        result = sanitize_error(msg)
        assert "1064" in result
        assert "SQL syntax" in result

    def test_empty_string(self) -> None:
        assert sanitize_error("") == ""

    def test_plain_string_unchanged(self) -> None:
        msg = "Something went wrong"
        assert sanitize_error(msg) == msg

    def test_strips_host_with_at_pattern(self) -> None:
        msg = "Connection refused trying to connect at dbhost.local:3306"
        result = sanitize_error(msg)
        assert "dbhost.local" not in result or "***" in result

    def test_error_without_connection_params(self) -> None:
        msg = "Table 'test.users' doesn't exist"
        result = sanitize_error(msg)
        assert msg in result
