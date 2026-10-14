# 文件说明：本文件属于 工具系统层。
# 主要职责：实现 execution 相关能力。
# 阅读提示：注册、执行和限制工具调用。
# 运行影响：仅用于源码阅读，不改变运行逻辑。

"""Tool execution engine."""

import asyncio
from typing import Any

from muxtrail.tools.policy import ToolPolicy
from muxtrail.tools.registry import ToolRegistry
from muxtrail.tools.types import ToolContext, ToolResult

DEFAULT_TOOL_TIMEOUT_SECONDS = 30.0


def _validate_params(schema: dict[str, Any], params: dict[str, object]) -> str | None:
    if schema.get("type") == "object" and not isinstance(params, dict):
        return "arguments must be an object"
    required = schema.get("required")
    if isinstance(required, list):
        missing = [str(name) for name in required if str(name) not in params]
        if missing:
            return f"missing required arguments: {', '.join(missing)}"
    properties = schema.get("properties")
    if not isinstance(properties, dict):
        return None
    type_map: dict[str, type[Any] | tuple[type[Any], ...]] = {
        "string": str,
        "integer": int,
        "number": (int, float),
        "boolean": bool,
        "array": list,
        "object": dict,
    }
    for name, value in params.items():
        rule = properties.get(name)
        if not isinstance(rule, dict):
            if schema.get("additionalProperties") is False:
                return f"unknown argument: {name}"
            continue
        expected = type_map.get(str(rule.get("type") or ""))
        if expected and not isinstance(value, expected):
            return f"argument '{name}' must be {rule.get('type')}"
        allowed = rule.get("enum")
        if isinstance(allowed, list) and value not in allowed:
            return f"argument '{name}' must be one of {allowed}"
    return None


async def execute_tool(
    registry: ToolRegistry,
    policy: ToolPolicy,
    name: str,
    params: dict[str, object],
    context: ToolContext | None = None,
) -> ToolResult:
    """Execute a tool by name with policy enforcement."""
    if not policy.is_allowed(name):
        return ToolResult(success=False, error=f"Tool '{name}' is denied by policy")

    tool = registry.get(name)
    if tool is None:
        return ToolResult(success=False, error=f"Tool '{name}' not found")

    if tool.handler is None:
        return ToolResult(success=False, error=f"Tool '{name}' has no handler")

    validation_error = _validate_params(tool.input_schema, params)
    if validation_error:
        return ToolResult(
            success=False, error=f"Invalid arguments for '{name}': {validation_error}"
        )

    try:
        async with asyncio.timeout(DEFAULT_TOOL_TIMEOUT_SECONDS):
            output = await tool.handler(params, context)
        return ToolResult(success=True, output=output)
    except TimeoutError:
        return ToolResult(success=False, error=f"Tool '{name}' timed out")
    except Exception as e:
        return ToolResult(success=False, error=str(e))
