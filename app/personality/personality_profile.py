from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PersonalityProfile:
    name: str
    mission: str
    tone: str
    style: str
    honesty: str
    humor: str
    voice: str
    verbosity: str
    temperature: str
    traits: tuple[str, ...]

    @classmethod
    def from_mapping(cls, values: dict) -> "PersonalityProfile":
        required = (
            "name", "mission", "tone", "style", "honesty", "humor",
            "voice", "verbosity", "temperature", "traits",
        )
        missing = [key for key in required if key not in values]
        if missing:
            raise ValueError(f"Missing personality fields: {', '.join(missing)}")
        traits = values["traits"]
        if not isinstance(traits, (list, tuple)):
            raise ValueError("Personality traits must be a list")
        return cls(**{key: str(values[key]).strip() for key in required[:-1]},
                   traits=tuple(str(value).strip().casefold() for value in traits))
