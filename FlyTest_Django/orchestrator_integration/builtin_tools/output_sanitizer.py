import re


_ANSI_ESCAPE_RE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")


def strip_terminal_control_sequences(text: str) -> str:
    return _ANSI_ESCAPE_RE.sub("", text or "")
