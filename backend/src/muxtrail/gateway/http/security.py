# 文件说明：本文件属于 Gateway 服务层。
# 主要职责：实现 security 相关能力。
# 阅读提示：承载 API、WebSocket 和运行事件。
# 运行影响：仅用于源码阅读，不改变运行逻辑。

"""Security middleware — CORS, headers."""

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from muxtrail.contracts.config.types_muxtrail import MuxTrailConfig

DEFAULT_ALLOWED_ORIGINS = [
    "http://127.0.0.1:3000",
    "http://127.0.0.1:3001",
    "http://localhost:3000",
    "http://localhost:3001",
]


def resolve_allowed_origins(config: MuxTrailConfig) -> list[str]:
    """Resolve exact browser origins from environment, config, or local defaults."""
    env_value = os.environ.get("MUXTRAIL_ALLOWED_ORIGINS", "")
    if env_value.strip():
        return [origin.strip().rstrip("/") for origin in env_value.split(",") if origin.strip()]

    control_ui = config.gateway.control_ui if config.gateway else None
    if control_ui and control_ui.allowed_origins:
        return [origin.rstrip("/") for origin in control_ui.allowed_origins]

    return list(DEFAULT_ALLOWED_ORIGINS)


def setup_security(app: FastAPI, allowed_origins: list[str]) -> None:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
