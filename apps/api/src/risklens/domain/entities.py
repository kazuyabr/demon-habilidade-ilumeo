"""Lightweight domain entities used across application services.

Persistence ORM models live in ``infrastructure.db.models``; these plain
dataclasses cross the ports layer so application services never touch
SQLAlchemy directly (DDD: domain layer has no infrastructure dependency).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID


@dataclass
class DocumentRef:
    id: UUID
    filename: str
    storage_path: str
    content_type: str
    sha256: str
    size_bytes: int


@dataclass
class ChunkInput:
    document_id: UUID
    chunk_index: int
    content: str
    metadata: dict = field(default_factory=dict)


@dataclass
class RetrievedChunk:
    document_id: UUID
    document_title: str
    content: str
    score: float
    metadata: dict = field(default_factory=dict)


@dataclass
class AgentStep:
    kind: str  # plan | retrieve | analyze | review | final
    thought: str | None = None
    action: str | None = None
    action_input: str | None = None
    observation: str | None = None
    output: str | None = None
    ts: str = field(default_factory=lambda: datetime.now().astimezone().isoformat())

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "thought": self.thought,
            "action": self.action,
            "action_input": self.action_input,
            "observation": self.observation,
            "output": self.output,
            "ts": self.ts,
        }
