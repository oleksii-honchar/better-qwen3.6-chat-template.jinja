#!/usr/bin/env python3
"""
Validate the better-qwen3.6-chat-template.jinja template.

Checks:
  1. Jinja2 syntax — template parses without errors
  2. Rendering — renders with various realistic inputs
  3. Output format — tool calls use Hermes JSON format, not XML

Usage:
  python3 validate-template.py [path/to/template.jinja]

  If no path is given, defaults to:
    /Users/oleksii.honchar/www/misc/better-qwen3.6-chat-template.jinja/better-qwen3.6-chat-template.jinja
"""

import json
import re
import sys
from pathlib import Path

import jinja2

DEFAULT_TEMPLATE = (
    "/Users/oleksii.honchar/www/misc/better-qwen3.6-chat-template.jinja/"
    "better-qwen3.6-chat-template.jinja"
)

# ---------------------------------------------------------------------------
# Custom Jinja environment
# ---------------------------------------------------------------------------

class TemplateError(Exception):
    """Raised by the raise_exception() Jinja helper."""
    pass

def _raise_exception(msg: str) -> str:
    raise TemplateError(msg)

def make_env() -> jinja2.Environment:
    return jinja2.Environment(
        loader=jinja2.BaseLoader(),
        undefined=jinja2.Undefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )

def load_template(path: str) -> jinja2.Template:
    env = make_env()
    source = Path(path).read_text(encoding="utf-8")
    return env.from_string(source, globals={"raise_exception": _raise_exception})

# ---------------------------------------------------------------------------
# Test scenarios — each returns a dict of template variables
# ---------------------------------------------------------------------------

def scenario_basic():
    return {
        "messages": [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ],
        "tools": None,
        "add_generation_prompt": False,
    }

def scenario_with_tools_and_tool_call():
    return {
        "messages": [
            {"role": "user", "content": "Read /etc/passwd"},
            {
                "role": "assistant",
                "content": "Let me read that file.",
                "tool_calls": [
                    {
                        "id": "call_abc",
                        "type": "function",
                        "function": {
                            "name": "read_file",
                            "arguments": {"path": "/etc/passwd"},
                        },
                    }
                ],
            },
        ],
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "read_file",
                    "description": "Read a file",
                    "parameters": {
                        "type": "object",
                        "properties": {"path": {"type": "string"}},
                        "required": ["path"],
                    },
                },
            }
        ],
        "add_generation_prompt": False,
    }

def scenario_tool_call_with_string_args():
    """Tool call where arguments is already a JSON string."""
    return {
        "messages": [
            {"role": "user", "content": "Search for 'hello world'"},
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "call_xyz",
                        "type": "function",
                        "function": {
                            "name": "search",
                            "arguments": '{"query": "hello world", "limit": 10}',
                        },
                    }
                ],
            },
        ],
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "search",
                    "description": "Search",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string"},
                            "limit": {"type": "integer"},
                        },
                        "required": ["query"],
                    },
                },
            }
        ],
        "add_generation_prompt": False,
    }

def scenario_tool_call_with_missing_args():
    """Tool call with no arguments key — should fallback to {}."""
    return {
        "messages": [
            {"role": "user", "content": "Ping"},
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "call_ping",
                        "type": "function",
                        "function": {"name": "ping"},
                    }
                ],
            },
        ],
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "ping",
                    "description": "Ping",
                    "parameters": {"type": "object", "properties": {}},
                },
            }
        ],
        "add_generation_prompt": False,
    }

def scenario_multi_tool_calls():
    """Assistant makes multiple tool calls in one message."""
    return {
        "messages": [
            {"role": "user", "content": "Read two files"},
            {
                "role": "assistant",
                "content": "I'll read both files.",
                "tool_calls": [
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {
                            "name": "read_file",
                            "arguments": {"path": "/tmp/a.txt"},
                        },
                    },
                    {
                        "id": "call_2",
                        "type": "function",
                        "function": {
                            "name": "read_file",
                            "arguments": {"path": "/tmp/b.txt"},
                        },
                    },
                ],
            },
        ],
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "read_file",
                    "description": "Read a file",
                    "parameters": {
                        "type": "object",
                        "properties": {"path": {"type": "string"}},
                        "required": ["path"],
                    },
                },
            }
        ],
        "add_generation_prompt": False,
    }

def scenario_with_reasoning():
    """Assistant with reasoning_content (thinking)."""
    return {
        "messages": [
            {"role": "user", "content": "What is 2+2?"},
            {
                "role": "assistant",
                "reasoning_content": "Let me think... 2+2 is 4.",
                "content": "2+2 equals 4.",
            },
        ],
        "tools": None,
        "add_generation_prompt": False,
    }

def scenario_tool_result():
    """Full tool-use cycle: user -> assistant (tool call) -> tool result -> assistant."""
    return {
        "messages": [
            {"role": "user", "content": "Read /tmp/a.txt"},
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {
                            "name": "read_file",
                            "arguments": {"path": "/tmp/a.txt"},
                        },
                    }
                ],
            },
            {
                "role": "tool",
                "content": "file contents here",
                "tool_call_id": "call_1",
            },
            {
                "role": "assistant",
                "content": "The file contains: file contents here",
            },
        ],
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "read_file",
                    "description": "Read a file",
                    "parameters": {
                        "type": "object",
                        "properties": {"path": {"type": "string"}},
                        "required": ["path"],
                    },
                },
            }
        ],
        "add_generation_prompt": False,
    }

def scenario_add_generation_prompt():
    """Ends with generation prompt (assistant prefix + thinking tag)."""
    return {
        "messages": [
            {"role": "user", "content": "Say hello"},
        ],
        "tools": None,
        "add_generation_prompt": True,
    }

def scenario_system_message():
    """Messages with a system/developer message."""
    return {
        "messages": [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi!"},
        ],
        "tools": None,
        "add_generation_prompt": False,
    }

def scenario_system_with_tools():
    """System message + tools — system content appended after tool instructions."""
    return {
        "messages": [
            {"role": "system", "content": "You are a file reader."},
            {"role": "user", "content": "Read /tmp/a.txt"},
        ],
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "read_file",
                    "description": "Read a file",
                    "parameters": {
                        "type": "object",
                        "properties": {"path": {"type": "string"}},
                        "required": ["path"],
                    },
                },
            }
        ],
        "add_generation_prompt": False,
    }

def scenario_image_content():
    """User message with image content."""
    return {
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "What is in this image?"},
                    {"type": "image_url", "image_url": {"url": "https://example.com/img.png"}},
                ],
            },
            {"role": "assistant", "content": "I see a cat."},
        ],
        "tools": None,
        "add_generation_prompt": False,
    }

def scenario_raise_exception():
    """Test that raise_exception works (system message not at beginning)."""
    return {
        "messages": [
            {"role": "user", "content": "Hello"},
            {"role": "system", "content": "Too late for system!"},
        ],
        "tools": None,
        "add_generation_prompt": False,
        "_expect_error": True,
    }

# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def assert_no_xml_tool_calls(output: str, name: str) -> None:
    """Ensure the output does NOT contain XML-style tool calls."""
    if re.search(r"<function=", output):
        raise AssertionError(f"[{name}] Found XML-style <function= tag — should be Hermes JSON")
    if re.search(r"<parameter=", output):
        raise AssertionError(f"[{name}] Found XML-style <parameter= tag — should be Hermes JSON")

def assert_hermes_json_tool_calls(output: str, name: str, expected_names: list[str]) -> None:
    """Ensure tool calls are in Hermes JSON format."""
    pattern = r'\{"name":\s*"([^"]+)",\s*"arguments":\s*(\{[^}]*\})\}'
    found = re.findall(pattern, output)
    found_names = [m[0] for m in found]

    if not found and expected_names:
        raise AssertionError(
            f"[{name}] Expected {len(expected_names)} Hermes JSON tool call(s), found 0"
        )

    for ename in expected_names:
        if ename not in found_names:
            raise AssertionError(
                f"[{name}] Expected tool call for '{ename}', found: {found_names}"
            )

def assert_tool_result_format(output: str, name: str) -> None:
    """Ensure tool results use the <tool_response> / </tool_response> format."""
    if "<tool_response>" not in output:
        raise AssertionError(f"[{name}] Expected <tool_response> tag in output")
    if "</tool_response>" not in output:
        raise AssertionError(f"[{name}] Expected </tool_response> tag in output")

def assert_generation_prompt(output: str, name: str) -> None:
    """Ensure generation prompt ends with assistant prefix + thinking tag."""
    stripped = output.rstrip()
    if not stripped.endswith("assistant\n<think>"):
        raise AssertionError(
            f"[{name}] Expected output to end with 'assistant\\n\\n</think>\\n\\n' for generation prompt, got: {stripped[-40:]!r}"
        )

def assert_no_double_escape(output: str, name: str) -> None:
    """Ensure string-arg tool calls are NOT double-escaped."""
    if '\\"name\\"' in output or '\\"arguments\\"' in output:
        raise AssertionError(f"[{name}] Found double-escaped quotes — string args were re-JSONified")

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run_scenario(template: jinja2.Template, scenario_name: str, kwargs: dict) -> None:
    """Render one scenario and run assertions."""
    expect_error = kwargs.pop("_expect_error", False)
    expected_tool_names = kwargs.pop("_expected_tool_names", [])

    try:
        output = template.render(**kwargs)
    except TemplateError as e:
        if expect_error:
            print(f"  OK — expected error: {e}")
            return
        raise AssertionError(f"[{scenario_name}] Unexpected error: {e}")

    # Basic checks for all non-error scenarios
    assert_no_xml_tool_calls(output, scenario_name)
    assert_no_double_escape(output, scenario_name)

    # Scenario-specific checks
    if expected_tool_names:
        assert_hermes_json_tool_calls(output, scenario_name, expected_tool_names)

    if "tool_result" in scenario_name:
        assert_tool_result_format(output, scenario_name)

    if "generation_prompt" in scenario_name:
        assert_generation_prompt(output, scenario_name)

    print(f"  OK")

def main() -> None:
    template_path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_TEMPLATE

    print(f"Template: {template_path}")
    print()

    # ------------------------------------------------------------------
    # Phase 1: Syntax check
    # ------------------------------------------------------------------
    print("Phase 1 — Jinja2 syntax check")
    try:
        tmpl = load_template(template_path)
        print("  OK — template parsed without errors")
    except jinja2.TemplateSyntaxError as e:
        print(f"  FAIL — syntax error: {e}")
        sys.exit(1)
    print()

    # ------------------------------------------------------------------
    # Phase 2: Render scenarios
    # ------------------------------------------------------------------
    print("Phase 2 — Render scenarios")
    scenarios = [
        ("basic", scenario_basic),
        ("system_message", scenario_system_message),
        ("with_tools_and_tool_call", scenario_with_tools_and_tool_call),
        ("tool_call_string_args", scenario_tool_call_with_string_args),
        ("tool_call_missing_args", scenario_tool_call_with_missing_args),
        ("multi_tool_calls", scenario_multi_tool_calls),
        ("with_reasoning", scenario_with_reasoning),
        ("tool_result", scenario_tool_result),
        ("add_generation_prompt", scenario_add_generation_prompt),
        ("system_with_tools", scenario_system_with_tools),
        ("image_content", scenario_image_content),
        ("raise_exception", scenario_raise_exception),
    ]

    failed = 0
    for sname, sfunc in scenarios:
        kwargs = sfunc()
        # Inject expected tool names for validation
        if "with_tools_and_tool_call" == sname:
            kwargs["_expected_tool_names"] = ["read_file"]
        elif "tool_call_string_args" == sname:
            kwargs["_expected_tool_names"] = ["search"]
        elif "tool_call_missing_args" == sname:
            kwargs["_expected_tool_names"] = ["ping"]
        elif "multi_tool_calls" == sname:
            kwargs["_expected_tool_names"] = ["read_file"]
        elif "tool_result" == sname:
            kwargs["_expected_tool_names"] = ["read_file"]

        try:
            run_scenario(tmpl, sname, kwargs)
        except AssertionError as e:
            print(f"  FAIL — {e}")
            failed += 1
        except Exception as e:
            print(f"  ERROR — [{sname}] {type(e).__name__}: {e}")
            failed += 1

    print()

    # ------------------------------------------------------------------
    # Phase 3: Summary
    # ------------------------------------------------------------------
    total = len(scenarios)
    if failed:
        print(f"Phase 3 — FAIL: {failed}/{total} scenario(s) failed")
        sys.exit(1)
    else:
        print(f"Phase 3 — PASS: all {total} scenarios passed")
        sys.exit(0)

if __name__ == "__main__":
    main()
