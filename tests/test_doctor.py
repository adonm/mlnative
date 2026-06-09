"""Tests for the diagnostic command."""

from mlnative.doctor import CheckResult, _format_result, run_checks


def test_format_result_marks_success():
    """Doctor output should be compact and human-readable."""
    assert _format_result(CheckResult("platform", True, "linux-x64")) == (
        "[ok] platform: linux-x64"
    )


def test_run_checks_without_render_is_safe():
    """Default diagnostics should not require starting the native renderer."""
    results = run_checks(render=False)
    names = [result.name for result in results]
    assert names == ["platform", "timeout", "binary"]
