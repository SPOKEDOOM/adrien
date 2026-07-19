from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Trait:
    name: str
    instruction: str


class TraitRegistry:
    DEFAULTS = {
        "concise": "Prefer concise answers and remove unnecessary repetition.",
        "technical": "Use accurate technical language when it helps the user.",
        "friendly": "Remain warm, respectful, and approachable.",
        "humorous": "Use occasional subtle humor when appropriate.",
        "teacher": "Explain unfamiliar ideas clearly and progressively.",
        "assistant": "Prioritize the user's request and provide practical next steps.",
        "coder": "Produce maintainable code and explain important tradeoffs.",
    }

    def __init__(self, traits: dict[str, str] | None = None) -> None:
        source = traits or self.DEFAULTS
        self._traits = {name: Trait(name, instruction) for name, instruction in source.items()}

    def get(self, name: str) -> Trait | None:
        return self._traits.get(name.casefold())

    def compose(self, names) -> tuple[Trait, ...]:
        composed, unknown = [], []
        for name in names:
            trait = self.get(str(name))
            if trait and trait not in composed: composed.append(trait)
            elif trait is None: unknown.append(str(name))
        if unknown: raise ValueError(f"Unknown personality traits: {', '.join(unknown)}")
        return tuple(composed)
