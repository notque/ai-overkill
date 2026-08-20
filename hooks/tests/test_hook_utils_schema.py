#!/usr/bin/env python3
"""Tests for schema-compatibility helpers in hook_utils.

Covers get_tool_result, get_tool_output, get_tool_error, and is_tool_error
across Claude/Codex and Factory CLI schemas.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))

from hook_utils import get_tool_error, get_tool_output, get_tool_result, is_tool_error

# ===== get_tool_result =====


def test_get_tool_result_claude_schema():
    event = {"hook_event_name": "PostToolUse", "tool_result": {"output": "hello", "is_error": False}}
    assert get_tool_result(event) == {"output": "hello", "is_error": False}


def test_get_tool_result_factory_schema():
    event = {"hook_event_name": "PostToolUse", "tool_response": {"stdout": "hello", "exitCode": 0}}
    assert get_tool_result(event) == {"stdout": "hello", "exitCode": 0}


def test_get_tool_result_neither_key():
    event = {"hook_event_name": "PostToolUse"}
    assert get_tool_result(event) == {}


def test_get_tool_result_preserves_content_blocks():
    blocks = [{"type": "text", "text": "hello"}]
    assert get_tool_result({"tool_response": blocks}) == blocks


# ===== get_tool_output =====


def test_get_tool_output_output_key():
    assert get_tool_output({"output": "from output"}) == "from output"


def test_get_tool_output_stdout_key():
    assert get_tool_output({"stdout": "from stdout"}) == "from stdout"


def test_get_tool_output_neither_key():
    assert get_tool_output({}) == ""


def test_get_tool_output_both_keys_output_wins():
    assert get_tool_output({"output": "output wins", "stdout": "stdout"}) == "output wins"


def test_get_tool_output_flattens_content_blocks():
    assert get_tool_output([{"type": "text", "text": "one"}, {"type": "text", "text": "two"}]) == "one\ntwo"


# ===== get_tool_error =====


def test_get_tool_error_explicit_error_key():
    assert get_tool_error({"error": "something failed"}) == "something failed"


def test_get_tool_error_exit_code_nonzero_with_stderr():
    result = {"exitCode": 1, "stderr": "bad error", "stdout": "some output"}
    assert get_tool_error(result) == "bad error"


def test_get_tool_error_exit_code_nonzero_only_stdout():
    result = {"exitCode": 2, "stderr": "", "stdout": "fallback output"}
    assert get_tool_error(result) == "fallback output"


def test_get_tool_error_exit_code_zero_no_error():
    assert get_tool_error({"exitCode": 0, "stderr": "", "stdout": "ok"}) == ""


def test_get_tool_error_explicit_error_empty_string():
    # Empty string for 'error' should not be treated as an error
    assert get_tool_error({"error": "", "exitCode": 0}) == ""


# ===== is_tool_error =====


def test_is_tool_error_is_error_true():
    assert is_tool_error({"is_error": True}) is True


def test_is_tool_error_is_error_false():
    assert is_tool_error({"is_error": False}) is False


def test_is_tool_error_exit_code_zero():
    assert is_tool_error({"exitCode": 0}) is False


def test_is_tool_error_exit_code_nonzero():
    assert is_tool_error({"exitCode": 1}) is True


def test_is_tool_error_neither_key():
    assert is_tool_error({}) is False


# ===== additional edge case tests =====


def test_get_tool_error_explicit_error_none():
    # None for 'error' is falsy, falls through to exitCode == 0 branch
    assert get_tool_error({"error": None, "exitCode": 0}) == ""


def test_get_tool_error_exit_nonzero_no_stderr_key():
    # No stderr key at all, default empty, falls through to stdout
    assert get_tool_error({"exitCode": 1, "stdout": "fallback"}) == "fallback"


def test_get_tool_output_empty_output_preserved():
    # Claude said empty output — we must not fall through to Factory's stdout
    assert get_tool_output({"output": "", "stdout": "ignored"}) == ""


def test_get_tool_result_empty_dict_preserved():
    # Claude said empty result — we must not fall through to Factory's tool_response
    assert get_tool_result({"tool_result": {}, "tool_response": {"x": 1}}) == {}
