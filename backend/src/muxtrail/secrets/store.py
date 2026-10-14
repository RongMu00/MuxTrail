# 文件说明：本文件属于 密钥管理层。
# 主要职责：实现 store 相关能力。
# 阅读提示：解析和存储敏感配置。
# 运行影响：仅用于源码阅读，不改变运行逻辑。

"""Local credential store at ~/.muxtrail-state/credentials/."""

import json
import re
from pathlib import Path
from typing import Any


class CredentialStore:
    """Simple file-based credential store."""

    def __init__(self, credentials_dir: Path) -> None:
        self.credentials_dir = credentials_dir

    def _path(self, name: str) -> Path:
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", name):
            raise ValueError("credential name contains unsupported characters")
        return self.credentials_dir / f"{name}.json"

    def read(self, name: str) -> dict[str, Any] | None:
        path = self._path(name)
        if not path.exists():
            return None
        data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        return data

    def write(self, name: str, data: dict[str, Any]) -> None:
        self.credentials_dir.mkdir(parents=True, exist_ok=True)
        self.credentials_dir.chmod(0o700)
        path = self._path(name)
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        path.chmod(0o600)

    def delete(self, name: str) -> bool:
        path = self._path(name)
        if path.exists():
            path.unlink()
            return True
        return False
