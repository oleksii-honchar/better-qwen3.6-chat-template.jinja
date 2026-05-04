# Better Qwen3.6 Chat Template

## Overview

A fixed version of the Qwen3.6 chat template that handles the "No user query found in messages" exception gracefully when DCP (Dynamic Context Pruning) removes user queries from the conversation history.

## Source

Original template with fixes from: https://huggingface.co/froggeric/Qwen-Fixed-Chat-Templates

## Problem

When DCP (Dynamic Context Pruning) compresses conversations, it may remove user query messages while keeping tool results. This causes the Qwen3.6 chat template to throw:

```
No user query found in messages.
```

### Root Cause

1. DCP configuration allowed user messages to be compressed (`protectUserMessages: false`)
2. Deduplication and error purge strategies removed all user queries
3. Only tool results remained, causing the template's strict validation to fail

## Changes Applied

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
| `qwen3.6-chat-template.jinja` | Fixed Jinja template (lines 89-102) |
| `README.md` | This documentation |

## Deferred Changes (Not Included)

| File | Change | Priority |
|------|--------|----------|
| `dcp.jsonc` | Enable `protectUserMessages: true` | P1 (Deferred) |

This change is purely defensive - it prevents the exception from being raised while preserving all existing functionality for normal conversations.

## Change Log

### 2026-05-02: Switched tool call format from XML to Hermes JSON

**Problem:** The template rendered tool calls in Qwen3-Coder XML format (`<function=name><parameter=arg>value</parameter></function>`), but `opencode`'s MCP tool-call handler expects Hermes JSON format. This caused `opencode: command not found` errors when `octocode-mcp` was enabled.

**Fix:** Replaced the XML tool-call rendering block (lines 161-186) with the Hermes JSON equivalent, and updated the tool instruction text (line 57) to reference the JSON format.

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

**After (Hermes JSON):**
```
␀
{"name": "read_file", "arguments": {"path": "/Users/foo"}}
␁
```

**Key changes:**
1. Removed ␀␁ XML tags - tool name and arguments are now encoded in a JSON object
2. Removed ␀␁ XML tags - arguments are serialized as a JSON object inside the "arguments" field
3. `arguments` is a raw JSON object, not a stringified JSON string
4. Double-escaping guard: when `tool_call.arguments` is already a string, it is used as-is; when it is a mapping, `tojson` is applied
5. Fallback for missing arguments: renders `"arguments": {}` instead of silently omitting

**Validation:**
- Jinja2 syntax validation passed (no TemplateSyntaxError)
- Functional test: rendered tool call output matches expected Hermes JSON format

**Session:** [260502-2113-fixing-tool-format](https://github.com/anthropics/anthropic-cookbook/tree/main/.agent-sessions/26/05/02/260502-2113-fixing-tool-format)
