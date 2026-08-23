import pytest

from genesis_cli.strip import MarkerError, declared_markers, strip_excluded

DOCKERFILE = """FROM python:3.13
# >>> module:jobs
RUN install temporal
# <<< module:jobs
RUN echo keep
"""

NESTED = """; >>> module:cache
; >>> service:valkey
[program:valkey]
; <<< service:valkey
; <<< module:cache
[program:nginx]
"""

MARKDOWN = """# Docs
<!-- >>> module:jobs -->
## Background jobs
<!-- <<< module:jobs -->
## Pages
"""


def test_block_removed_when_excluded():
    assert "temporal" not in strip_excluded(DOCKERFILE, {"module:jobs"})
    assert "RUN echo keep" in strip_excluded(DOCKERFILE, {"module:jobs"})


def test_block_kept_when_included():
    assert strip_excluded(DOCKERFILE, set()) == DOCKERFILE


def test_line_tag_removed():
    text = 'a = 1 # module:ai\nb = 2\n'
    assert strip_excluded(text, {"module:ai"}) == "b = 2\n"


def test_nested_block_removed_by_outer_marker():
    stripped = strip_excluded(NESTED, {"module:cache"})
    assert "valkey" not in stripped
    assert "[program:nginx]" in stripped


def test_nested_block_removed_by_inner_marker_keeps_outer():
    stripped = strip_excluded(NESTED, {"service:valkey"})
    assert "[program:valkey]" not in stripped
    assert "module:cache" in stripped


def test_html_comment_markers():
    stripped = strip_excluded(MARKDOWN, {"module:jobs"})
    assert "Background jobs" not in stripped
    assert "## Pages" in stripped


def test_unclosed_block_raises():
    with pytest.raises(MarkerError, match="unclosed"):
        strip_excluded("# >>> module:jobs\nx\n", set())


def test_mismatched_close_raises():
    with pytest.raises(MarkerError, match="is open"):
        strip_excluded("# >>> module:jobs\n# <<< module:ai\n", set())


def test_orphan_close_raises():
    with pytest.raises(MarkerError, match="no opener"):
        strip_excluded("# <<< module:jobs\n", set())


def test_declared_markers_finds_all_kinds():
    text = "# >>> module:jobs\n# <<< module:jobs\nx = 1 # service:valkey\n"
    assert declared_markers(text) == {"module:jobs", "service:valkey"}
