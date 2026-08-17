#!/usr/bin/env python3
"""
Validate the better-qwen3.6-chat-template.jinja template.

Checks:
  1. Jinja2 syntax — template parses without errors
  2. Rendering — renders with various realistic inputs
  3. Output format — tool calls use XML format (<tool_call><function=...><parameter=...>)
  4. Reasoning effort (3.8 template only) — instruction injection/omission and
     exception behavior per materials/design-qwen38-template.md §"Validation scenarios"

Usage:
  python3 validate-template.py [path/to/template.jinja]

  If no path is given, defaults to:
    /Users/oleksii.honchar/www/misc/better-qwen3.6-chat-template.jinja/better-qwen3.6-chat-template.jinja
"""

import re
import sys
from pathlib import Path

import jinja2

DEFAULT_TEMPLATE = (
    "/Users/oleksii.honchar/www/misc/better-qwen3.6-chat-template.jinja/"
    "better-qwen3.6-chat-template.jinja"
)

# Reasoning-effort instruction texts (verbatim from the native Qwen3.8 template).
XHIGH_INSTRUCTION = (
    "Reasoning effort is set to xhigh. Please think carefully through the task, "
    "validate key assumptions, consider plausible alternatives, and prioritize "
    "correctness, consistency, and clarity in the final answer."
)
LOW_INSTRUCTION = (
    "Reasoning effort is set to low. Keep your thinking brief and focused, "
    "moving directly to the conclusion without unnecessary elaboration."
)
ALL_INSTRUCTIONS = (XHIGH_INSTRUCTION, LOW_INSTRUCTION)

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

def has_effort_support(source: str) -> bool:
    """True when the template implements the reasoning_effort block (3.8+).
    Detected from template source so the check stays valid regardless of the
    file's name: the 3.6 template contains no 'reasoning_effort' references and
    therefore skips the effort scenarios; the 3.8 template runs them fully.
    """
    return "reasoning_effort" in source

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

def _effort_tools():
    """Minimal tools definition shared by effort tool scenarios."""
    return [
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
    ]

def _effort_base_kwargs():
    return {
        "messages": [{"role": "user", "content": "Hello"}],
        "tools": None,
        "add_generation_prompt": False,
    }

def scenario_effort_default_xhigh():
    """Effort undefined + thinking on -> xhigh instruction injected (native default)."""
    return {
        **_effort_base_kwargs(),
        "_expected_instruction": XHIGH_INSTRUCTION,
    }

def scenario_effort_medium():
    """Effort=medium -> valid value, but NO instruction injected."""
    return {
        **_effort_base_kwargs(),
        "reasoning_effort": "medium",
        "_expected_no_instruction": True,
    }

def scenario_effort_low():
    """Effort=low -> low instruction injected."""
    return {
        **_effort_base_kwargs(),
        "reasoning_effort": "low",
        "_expected_instruction": LOW_INSTRUCTION,
    }

def scenario_effort_xhigh():
    """Effort=xhigh -> xhigh instruction injected."""
    return {
        **_effort_base_kwargs(),
        "reasoning_effort": "xhigh",
        "_expected_instruction": XHIGH_INSTRUCTION,
    }

def scenario_effort_high_remap():
    """Effort=high -> remapped to xhigh (xhigh instruction, no error)."""
    return {
        **_effort_base_kwargs(),
        "reasoning_effort": "high",
        "_expected_instruction": XHIGH_INSTRUCTION,
    }

def scenario_effort_invalid():
    """Effort=bogus + thinking on -> TemplateError with native message."""
    return {
        **_effort_base_kwargs(),
        "reasoning_effort": "bogus",
        "_expect_error": True,
        "_expected_error_message": "Unexpected reasoning effort bogus",
    }

def scenario_effort_thinking_off_low():
    """Thinking off + effort=low -> no instruction (effort gated by thinking)."""
    return {
        **_effort_base_kwargs(),
        "enable_thinking": False,
        "reasoning_effort": "low",
        "_expected_no_instruction": True,
    }

def scenario_effort_thinking_off_bogus():
    """Thinking off + effort=bogus -> no error AND no instruction (gated, native)."""
    return {
        **_effort_base_kwargs(),
        "enable_thinking": False,
        "reasoning_effort": "bogus",
        "_expected_no_instruction": True,
    }

def scenario_effort_tools_xhigh():
    """Tools + effort=xhigh -> instruction appears BEFORE the # Tools block."""
    return {
        "messages": [{"role": "user", "content": "Hello"}],
        "tools": _effort_tools(),
        "add_generation_prompt": False,
        "reasoning_effort": "xhigh",
        "_expected_instruction": XHIGH_INSTRUCTION,
        "_expected_instruction_before": "# Tools",
    }

# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def assert_xml_tool_calls(output: str, name: str, expected_names: list[str], expected_parameters: list[str]) -> None:
    """Ensure tool calls are in Qwen XML format:
    <tool_call><function=name><parameter=arg>value</parameter></function></tool_call>."""
    if "<tool_call>" not in output:
        raise AssertionError(f"[{name}] Expected <tool_call> XML tag in output")
    if "</tool_call>" not in output:
        raise AssertionError(f"[{name}] Expected </tool_call> closing tag in output")

    for ename in expected_names:
        if f"<function={ename}>" not in output:
            raise AssertionError(f"[{name}] Expected <function={ename}> XML tag in output")
    if not re.search(r"</function>", output):
        raise AssertionError(f"[{name}] Expected </function> closing tag in output")

    for pname in expected_parameters:
        if f"<parameter={pname}>" not in output:
            raise AssertionError(f"[{name}] Expected <parameter={pname}> XML tag in output")
        if f"</parameter>" not in output:
            raise AssertionError(f"[{name}] Expected </parameter> closing tag in output")

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
    expected_parameters = kwargs.pop("_expected_parameters", [])
    expected_instruction = kwargs.pop("_expected_instruction", None)
    expected_no_instruction = kwargs.pop("_expected_no_instruction", False)
    expected_instruction_before = kwargs.pop("_expected_instruction_before", None)
    expected_error_message = kwargs.pop("_expected_error_message", None)

    try:
        output = template.render(**kwargs)
    except TemplateError as e:
        if expect_error:
            if expected_error_message and expected_error_message not in str(e):
                raise AssertionError(
                    f"[{scenario_name}] Expected error containing {expected_error_message!r}, got: {e}"
                )
            print(f"  OK — expected error: {e}")
            return
        raise AssertionError(f"[{scenario_name}] Unexpected error: {e}")

    if expect_error:
        raise AssertionError(
            f"[{scenario_name}] Expected TemplateError, but template rendered successfully"
        )

    # Basic checks for all non-error scenarios
    assert_no_double_escape(output, scenario_name)

    # Reasoning-effort checks (rendered-output behavior only)
    if expected_instruction:
        if expected_instruction not in output:
            raise AssertionError(
                f"[{scenario_name}] Expected reasoning-effort instruction in output"
            )
        if expected_instruction_before:
            if expected_instruction_before not in output:
                raise AssertionError(
                    f"[{scenario_name}] Expected marker {expected_instruction_before!r} in output"
                )
            if output.index(expected_instruction) > output.index(expected_instruction_before):
                raise AssertionError(
                    f"[{scenario_name}] Instruction must appear BEFORE "
                    f"{expected_instruction_before!r}"
                )

    if expected_no_instruction:
        for instr in ALL_INSTRUCTIONS:
            if instr in output:
                raise AssertionError(
                    f"[{scenario_name}] Expected no reasoning-effort instruction, found one"
                )

    # Scenario-specific checks
    if expected_tool_names:
        assert_xml_tool_calls(output, scenario_name, expected_tool_names, expected_parameters)

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

    if has_effort_support(Path(template_path).read_text(encoding="utf-8")):
        scenarios.extend([
            ("effort_default_xhigh", scenario_effort_default_xhigh),
            ("effort_medium", scenario_effort_medium),
            ("effort_low", scenario_effort_low),
            ("effort_xhigh", scenario_effort_xhigh),
            ("effort_high_remap", scenario_effort_high_remap),
            ("effort_invalid", scenario_effort_invalid),
            ("effort_thinking_off_low", scenario_effort_thinking_off_low),
            ("effort_thinking_off_bogus", scenario_effort_thinking_off_bogus),
            ("effort_tools_xhigh", scenario_effort_tools_xhigh),
        ])
    else:
        print("  (template has no reasoning_effort block — effort scenarios skipped)")

    failed = 0
    for sname, sfunc in scenarios:
        kwargs = sfunc()
        # Inject expected tool names + parameters for validation
        if "with_tools_and_tool_call" == sname:
            kwargs["_expected_tool_names"] = ["read_file"]
            kwargs["_expected_parameters"] = ["path"]
        elif "tool_call_string_args" == sname:
            kwargs["_expected_tool_names"] = ["search"]
        elif "tool_call_missing_args" == sname:
            kwargs["_expected_tool_names"] = ["ping"]
        elif "multi_tool_calls" == sname:
            kwargs["_expected_tool_names"] = ["read_file"]
            kwargs["_expected_parameters"] = ["path"]
        elif "tool_result" == sname:
            kwargs["_expected_tool_names"] = ["read_file"]
            kwargs["_expected_parameters"] = ["path"]

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
