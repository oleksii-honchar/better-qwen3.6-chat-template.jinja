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
