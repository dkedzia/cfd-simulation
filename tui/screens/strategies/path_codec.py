from __future__ import annotations

import base64
import json

from strategy.ir import EditorPath


def encode_path(path: EditorPath) -> str:
    raw = json.dumps(list(path), separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii")


def decode_path(raw: str) -> EditorPath:
    data = json.loads(base64.urlsafe_b64decode(raw.encode("ascii")))
    return tuple(data)
