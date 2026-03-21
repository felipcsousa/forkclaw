from __future__ import annotations

import json
import sys
from typing import Any

from app.db.migrations import upgrade_database
from app.db.session import get_db_session
from app.schemas.acp import (
    AcpLoadSessionRequest,
    AcpNewSessionRequest,
    AcpPromptRequest,
)
from app.services.acp import AcpService


def _response_ok(request_id: Any, result: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _response_error(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def _handle_method(method: str, params: dict[str, Any]) -> dict[str, Any]:
    with get_db_session() as session:
        service = AcpService(session)

        if method == "initialize":
            return {
                "protocol": "acp",
                "version": "1.0",
                "enabled": service.is_enabled(),
                "capabilities": {
                    "methods": [
                        "initialize",
                        "newSession",
                        "listSessions",
                        "loadSession",
                        "prompt",
                        "cancel",
                    ]
                },
            }

        if method == "newSession":
            payload = AcpNewSessionRequest.model_validate(params)
            created = service.create_session(
                label=payload.label,
                runtime=payload.runtime,
                parent_session_id=payload.parent_session_id,
            )
            return created.model_dump(mode="json")

        if method == "listSessions":
            items = service.list_sessions()
            return {"items": [item.model_dump(mode="json") for item in items]}

        if method == "loadSession":
            payload = AcpLoadSessionRequest.model_validate(params)
            loaded = service.load_session(session_key=payload.session_key, limit=payload.limit)
            return loaded.model_dump(mode="json")

        if method == "prompt":
            payload = AcpPromptRequest.model_validate(params)
            result = service.prompt(session_key=payload.session_key, text=payload.text)
            return result.model_dump(mode="json")

        if method == "cancel":
            session_key = str(params.get("session_key") or "").strip()
            if not session_key:
                msg = "session_key is required."
                raise ValueError(msg)
            result = service.cancel(session_key=session_key)
            return result.model_dump(mode="json")

    msg = f"Method not found: {method}"
    raise ValueError(msg)


def main() -> None:
    upgrade_database()
    for raw_line in sys.stdin:
        line = raw_line.strip()
        if not line:
            continue
        request_id: Any = None
        try:
            payload = json.loads(line)
            if not isinstance(payload, dict):
                raise ValueError("Payload must be a JSON object.")
            request_id = payload.get("id")
            method = str(payload.get("method") or "").strip()
            if not method:
                raise ValueError("method is required.")
            params = payload.get("params") or {}
            if not isinstance(params, dict):
                raise ValueError("params must be an object.")
            result = _handle_method(method, params)
            print(json.dumps(_response_ok(request_id, result), ensure_ascii=False), flush=True)
        except Exception as exc:
            print(
                json.dumps(_response_error(request_id, -32000, str(exc)), ensure_ascii=False),
                flush=True,
            )


if __name__ == "__main__":
    main()
