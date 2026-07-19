from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class PersonalityConfig:
    profile_path: str | None = None
    name: str = "ADRIEN"
    tone: str = "professional"
    verbosity: str = "medium"
    humor: str = "low"
    honesty: str = "strict"
    default_traits: tuple[str, ...] = field(
        default_factory=lambda: ("assistant", "friendly", "technical")
    )
