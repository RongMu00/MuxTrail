# 文件说明：本文件属于 Agent 模型运行层。
# 主要职责：实现 builder 相关能力。
# 阅读提示：组织模型运行、工具循环和提示词组合。
# 运行影响：仅用于源码阅读，不改变运行逻辑。

"""System prompt builder."""

from typing import Any

DEFAULT_MUXTRAIL_IDENTITY = (
    "You are the MuxTrail assistant, running through an observable local-first AI gateway. "
    "Use the active session history for multi-turn memory and accurately recall information "
    "the user supplied in this session. Never claim that active-session memory is unavailable. "
    "Use allowed tools as structured actions, inspect tool results, and continue until you can "
    "give a normal user-facing answer. Never expose raw tool-call JSON as the final answer unless "
    "the user explicitly asks for debugging output. A failed or zero-result search is not evidence "
    "that an event did not happen or that information does not exist. Cite only sources actually "
    "returned and read by tools. Be transparent about errors and uncertainty. Respond in English "
    "by default, matching the user's language when helpful. Never identify yourself as another "
    "assistant or product."
)


def build_system_prompt(
    identity: str = DEFAULT_MUXTRAIL_IDENTITY,
    channel_context: str | None = None,
    tool_descriptions: list[dict[str, Any]] | None = None,
    tool_instructions: list[str] | None = None,
    extra: str | None = None,
) -> str:
    parts = [identity]
    if channel_context:
        parts.append(f"\n{channel_context}")
    if tool_descriptions:
        tool_text = "\n".join(
            f"- {t['name']}: {t.get('description', '')}" for t in tool_descriptions
        )
        parts.append(f"\nAvailable tools:\n{tool_text}")
    if tool_instructions:
        instructions = [item.strip() for item in tool_instructions if item.strip()]
        if instructions:
            parts.append("\nTool usage rules:\n" + "\n\n".join(instructions))
    if extra:
        parts.append(f"\n{extra}")
    return "\n".join(parts)
