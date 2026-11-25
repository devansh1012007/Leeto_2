"""T-10.7: attack-like report text must NOT be blocked — it is legitimate content (NET-02).
Runs the corpus through the API's validation layer and asserts acceptance."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

CORPUS = [
    "SQL injection: ' OR 1=1-- bypasses auth in login()",
    "XSS stored in profile: <script>alert(1)</script> renders on the admin view",
    "Command injection: ; rm -rf / via the filename parameter",
    "Path traversal: ../../etc/passwd readable through the download endpoint",
    "SSRF: http://169.254.169.254/latest/meta-data/ reachable from the preview feature",
    "Template injection: {{7*7}} evaluates in the email template",
]


def test_corpus_survives_validation():
    """The API validates structure (file/lines/lengths) — never content keywords."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))
    from submissions.pipeline import _validate_flag

    for text in CORPUS:
        flag = {"file": "src/app.py", "lines": "12-18", "explanation": text}
        _validate_flag(flag, {"max_span": 25})  # must NOT raise: content is data (NET-02)
