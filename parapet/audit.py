"""Append-only, hash-chained audit log.

Every observation, decision and action the agent takes is written here with the
reasoning inputs, so a reviewer (or regulator) can replay why the agent acted.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


class AuditLog:
    def __init__(self, path: Optional[Path] = None):
        self.path = path
        self.entries: list[dict[str, Any]] = []
        self._prev_hash = "0" * 64
        if path:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("")

    def record(self, event: str, **data: Any) -> dict[str, Any]:
        entry = {
            "seq": len(self.entries) + 1,
            "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "event": event,
            "prev_hash": self._prev_hash,
            **data,
        }
        payload = json.dumps(entry, sort_keys=True, default=str).encode()
        entry["hash"] = hashlib.sha256(payload).hexdigest()
        self._prev_hash = entry["hash"]
        self.entries.append(entry)
        if self.path:
            with self.path.open("a") as f:
                f.write(json.dumps(entry, default=str) + "\n")
        return entry

    def verify_chain(self) -> bool:
        prev = "0" * 64
        for e in self.entries:
            body = {k: v for k, v in e.items() if k != "hash"}
            if body["prev_hash"] != prev:
                return False
            h = hashlib.sha256(json.dumps(body, sort_keys=True, default=str).encode()).hexdigest()
            if h != e["hash"]:
                return False
            prev = h
        return True
