# 文件说明：本文件属于 契约层。
# 主要职责：把外部能力适配为统一插件。
# 阅读提示：定义跨模块共享的数据结构。
# 运行影响：仅用于源码阅读，不改变运行逻辑。

"""ChannelPlugin Protocol — the interface all channels must implement.

Matches TS ChannelPlugin in src/channels/plugins/types.plugin.ts.
"""

from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field


class ChannelMeta(BaseModel):
    """Channel metadata for display and discovery."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    id: str
    label: str
    selection_label: str = Field(alias="selectionLabel")
    docs_path: str = Field(alias="docsPath")
    blurb: str
    aliases: list[str] | None = None
    markdown_capable: bool | None = Field(default=None, alias="markdownCapable")
    order: int | None = None


class ChannelCapabilities(BaseModel):
    """What the channel supports."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    chat_types: list[str] = Field(alias="chatTypes")  # "dm", "group", "channel", "thread"
    polls: bool | None = None
    reactions: bool | None = None
    edit: bool | None = None
    unsend: bool | None = None
    reply: bool | None = None
    threads: bool | None = None
    media: bool | None = None
    block_streaming: bool | None = Field(default=None, alias="blockStreaming")


class InboundMessage(BaseModel):
    """Normalized inbound message from any channel."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    channel: str
    account_id: str = Field(alias="accountId")
    workspace_id: str | None = Field(default=None, alias="workspaceId")
    sender_id: str = Field(alias="senderId")
    conversation_id: str = Field(alias="conversationId")
    text: str | None = None
    attachments: list[dict[str, Any]] | None = None
    thread_id: str | None = Field(default=None, alias="threadId")
    message_id: str | None = Field(default=None, alias="messageId")
    reply_target: str | None = Field(default=None, alias="replyTarget")
    trace_id: str | None = Field(default=None, alias="traceId")
    chat_type: str = Field(default="dm", alias="chatType")
    unsupported_content: list[dict[str, Any]] | None = Field(
        default=None, alias="unsupportedContent"
    )
    capabilities: dict[str, Any] | None = None
    raw: dict[str, Any] | None = None


class OutboundMessage(BaseModel):
    """Normalized outbound message to any channel."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    text: str | None = None
    media_urls: list[str] | None = Field(default=None, alias="mediaUrls")
    reply_to_id: str | None = Field(default=None, alias="replyToId")
    thread_id: str | None = Field(default=None, alias="threadId")
    trace_id: str | None = Field(default=None, alias="traceId")
    channel_data: dict[str, Any] | None = Field(default=None, alias="channelData")


class DeliveryResult(BaseModel):
    """Normalized channel delivery outcome for tracing and diagnostics."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    ok: bool
    channel: str
    message_ids: list[str] = Field(default_factory=list, alias="messageIds")
    status_code: int | None = Field(default=None, alias="statusCode")
    error: str | None = None
    retry_count: int = Field(default=0, alias="retryCount")


@runtime_checkable
class ChannelPlugin(Protocol):
    """Interface that all channel implementations must satisfy."""

    @property
    def id(self) -> str: ...

    @property
    def meta(self) -> ChannelMeta: ...

    @property
    def capabilities(self) -> ChannelCapabilities: ...

    def list_account_ids(self, config: dict[str, Any]) -> list[str]: ...

    async def start(self, account_id: str, config: dict[str, Any]) -> None: ...

    async def stop(self, account_id: str) -> None: ...

    async def send(
        self, account_id: str, conversation_id: str, message: OutboundMessage
    ) -> None: ...
