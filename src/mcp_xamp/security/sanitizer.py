"""Sanitize error messages by stripping connection details."""

import re


def sanitize_error(exc: BaseException | str) -> str:
    """Remove host, port, user, password, and IP information from *exc*.

    Keeps SQL error codes and generic descriptions intact.
    """
    msg = str(exc)

    # host patterns:  "host 'something'"  /  "on 'something'"
    msg = re.sub(r"\bhost\s+'[^']*'", "host '***'", msg, flags=re.IGNORECASE)
    msg = re.sub(r"\bon\s+'[^']*'", "on '***'", msg, flags=re.IGNORECASE)
    msg = re.sub(r"at\s+\S+:\d+", "at ***", msg)

    # user patterns
    msg = re.sub(r"\buser\s+'[^']*'", "user '***'", msg, flags=re.IGNORECASE)
    msg = re.sub(r"'[^']*'@'[^']*'", "'***'@'***'", msg)

    # password patterns — process "using password:" before generic "password:"/"="
    msg = re.sub(r"using password:\s*\S+", "using password: ***", msg, flags=re.IGNORECASE)
    msg = re.sub(r"\bpassword\s*=\s*\S+", "password=***", msg, flags=re.IGNORECASE)

    # IP addresses
    msg = re.sub(r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}", "***", msg)

    # port numbers (standalone, after common keywords)
    msg = re.sub(r"\bport\s+\d+", "port ***", msg, flags=re.IGNORECASE)

    return msg.strip()
