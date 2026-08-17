# Better Qwen Chat Template

Generic Qwen chat template repo (renamed from `better-qwen3.6-chat-template.jinja`).
Provides fixed Qwen3.6 and Qwen3.8 chat templates that handle the "No user query
found in messages" exception gracefully when DCP (Dynamic Context Pruning) removes
user queries from the conversation history — and, in the 3.8 version, consume a
`reasoning_effort` knob to steer the model's reasoning effort.

## Source

Original template with fixes from: https://huggingface.co/froggeric/Qwen-Fixed-Chat-Templates

## Active Template Versions

| File | Version | XML tool calls | DCP-safe | `reasoning_effort` |
|------|---------|----------------|----------|--------------------|
| `better-qwen3.6-chat-template.jinja` | v2 | ✅ | ✅ | — |
| `better-qwen3.8-chat-template.jinja` | v2 + effort block | ✅ | ✅ | ✅ |

**Differences:**

- **`better-qwen3.6-chat-template.jinja`** — the current v2 template (byte-identical
  to the previous `better-qwen-chat-template.jinja`, only renamed). XML tool calls,
  DCP-safe `found_user_query` handling, `<think>` markers, litellm-compatible
  rendering. No `reasoning_effort` support.
- **`better-qwen3.8-chat-template.jinja`** — identical v2 base **plus** a
  `reasoning_effort` block. Consumes `reasoning_effort` from the jinja context
  (via `chat_template_kwargs`), defaults to `xhigh`, remaps `high` → `xhigh`,
  raises on invalid values (when thinking is enabled), and injects the native
  reasoning-effort instruction into the system message. Use this file for
  Qwen3.8 models that should honor reasoning effort; keep 3.6 models on the 3.6
  file.

## `reasoning_effort` contract (3.8 only)

Read from `chat_template_kwargs.reasoning_effort` (the jinja context var).

| Value | Result |
|-------|--------|
| *(undefined)* | default `xhigh` → xhigh instruction injected |
| `xhigh` | xhigh instruction injected |
| `medium` | no instruction injected (valid, steering text empty) |
| `low` | low instruction injected |
| `high` | **remapped to `xhigh`** → xhigh instruction injected (deliberate extension; native Qwen3.8 raises on `high`) |
| anything else + thinking on | `TemplateError`: `Unexpected reasoning effort <value>. Supported types are xhigh (default), medium, and low.` |
| anything + thinking off (`enable_thinking: false`) | effort ignored entirely — no instruction, no error |

**Thinking-off switch:** use `enable_thinking: false` in `chat_template_kwargs`.
Do **not** use `reasoning_effort: none` — `none` is not a valid effort value and
is not how thinking is disabled.

Instruction texts (verbatim from native Qwen3.8 tokenizer_config.json):

- **xhigh:** `Reasoning effort is set to xhigh. Please think carefully through the task, validate key assumptions, consider plausible alternatives, and prioritize correctness, consistency, and clarity in the final answer.`
- **low:** `Reasoning effort is set to low. Keep your thinking brief and focused, moving directly to the conclusion without unnecessary elaboration.`

Injection placement mirrors native: with tools, the instruction is emitted in the
system message **before** the `# Tools` block; without tools, it is prepended to
the system content (or emitted as a standalone system message when no system
message exists).

## Tool Call Format (XML)

The templates render tool calls in Qwen XML format:

```
<tool_call>
<function=read_file>
<parameter=path>
/tmp/a.txt
</parameter>
</function>
</tool_call>
```

**Key points:**
1. Each tool call is wrapped in a `<tool_call>...</tool_call>` block
2. The function name is emitted as `<function=name>...</function>`
3. Mapping arguments become `<parameter=arg>value</parameter>` entries
4. String-form arguments are emitted verbatim (no re-JSONification, no double escaping)
5. Missing arguments render the function block with no `<parameter>` entries

## Usage

Serve the template file to llama.cpp with `--chat-template-file`, and pass the
effort knob (3.8 only) via `chat_template_kwargs`:

```bash
# Qwen3.8 with xhigh reasoning effort
llama-server \
  --model /models/qwen3.8-27b.gguf \
  --jinja \
  --chat-template-file /models/better-qwen3.8-chat-template.jinja \
  ...
```

```json
// Request body (chat_template_kwargs carries the custom effort values)
{
  "model": "qwen38-27b-xhigh",
  "chat_template_kwargs": {
    "enable_thinking": true,
    "preserve_thinking": true,
    "reasoning_effort": "xhigh"
  }
}
```

> At the pinned llama.cpp, top-level `reasoning_effort` in the request body is
> discarded (only `"none"` is handled). The **only reliable path** is
> `chat_template_kwargs` → jinja context var → template.

## Problem

When DCP (Dynamic Context Pruning) compresses conversations, it may remove user query messages while keeping tool results. This causes the Qwen3.6 chat template to throw:

```
No user query found in messages.
```

### Root Cause

1. DCP configuration allowed user messages to be compressed (`protectUserMessages: false`)
2. Deduplication and error purge strategies removed all user queries
3. Only tool results remained, causing the template's strict validation to fail

## Changes Applied (DCP fix, both active versions)

### 1. Added `found_user_query` flag (Line 89)

**Before:**
```jinja
{%- set ns = namespace(multi_step_tool=true, last_query_index=messages|length - 1) %}
```

**After:**
```jinja
{%- set ns = namespace(multi_step_tool=true, last_query_index=messages|length - 1, found_user_query=false) %}
```

### 2. Set flag when user query is found (Line 97)

**Added:**
```jinja
{%- set ns.found_user_query = true %}
```

When a valid user query is found (non-`<tool_response>` content), the flag is set to `true`.

### 3. Graceful degradation instead of exception (Lines 101-104)

**Before:**
```jinja
{%- if ns.multi_step_tool %}
    {{- raise_exception('No user query found in messages.') }}
{%- endif %}
```

**After:**
```jinja
{%- if ns.multi_step_tool %}
    {%- if not ns.found_user_query %}
        {%- set ns.multi_step_tool = false %}
    {%- endif %}
{%- endif %}
```

## Behavior After Fix

| Scenario | `multi_step_tool` | `found_user_query` | Result |
|----------|-------------------|--------------------|--------|
| Normal conversation | `false` | `true` | Standard rendering |
| Tool-result-only (post-DCP) | `false` | `false` | No exception, standard rendering |

## Files

| File | Description |
|------|-------------|
| `better-qwen3.6-chat-template.jinja` | Active Qwen3.6 template (v2, XML tool calls, DCP-safe) |
| `better-qwen3.8-chat-template.jinja` | Active Qwen3.8 template (v2 + `reasoning_effort` block) |
| `validate-template.py` | Test harness — XML tool-call assertions + effort scenarios (3.8) |
| `better-qwen-chat-template-v1.jinja` | Historical archive (v1) |
| `better-qwen-chat-template-v2.jinja` | Historical archive (v2, superseded by the renamed active 3.6 file) |
| `froggeric-qwen-chat-template-v19.jinja` | Historical archive (froggeric upstream) |
| `README.md` | This documentation |

## Archive Files (historical)

`better-qwen-chat-template-v1.jinja`, `better-qwen-chat-template-v2.jinja`, and
`froggeric-qwen-chat-template-v19.jinja` are kept for history. The **active**
templates are `better-qwen3.6-chat-template.jinja` and
`better-qwen3.8-chat-template.jinja`.

## Deferred Changes (Not Included)

| File | Change | Priority |
|------|--------|----------|
| `dcp.jsonc` | Enable `protectUserMessages: true` | P1 (Deferred) |

This change is purely defensive - it prevents the exception from being raised while preserving all existing functionality for normal conversations.

## Change Log

### 2026-08-17: Repo renamed to generic `better-qwen-chat-template`

The repo is now generic: the previous `better-qwen-chat-template.jinja` file was
renamed to `better-qwen3.6-chat-template.jinja` (byte-identical v2), and a new
`better-qwen3.8-chat-template.jinja` was added with `reasoning_effort` support.
Sibling doc moved to `better-qwen-chat-template.md`.

### 2026-08-17: Tool call format is XML (documented reality)

The templates render tool calls in Qwen XML format (`<tool_call><function=...><parameter=...>`). The validator (`validate-template.py`) asserts this XML format for all tool-call scenarios. See the "Tool Call Format" section above.

**Validation:**
- Jinja2 syntax validation passed (no TemplateSyntaxError)
- Functional test: all tool-call scenarios render XML tags and pass the validator

### 2026-05-02 (historical): Tool call format was briefly Hermes JSON

> Note: This entry describes a short-lived experiment. Commit `4a06c92` ("fix: force qwen xml for tool call") reverted the template to XML tool calls; the validator and this README now reflect the XML reality.

**Before (XML):**
```
␀
<function=read_file>
<parameter=path>
/Users/foo
</parameter>
</function>
␁
```

**After (Hermes JSON) — NOT current:**
```
␀
{"name": "read_file", "arguments": {"path": "/Users/foo"}}
␁
```
