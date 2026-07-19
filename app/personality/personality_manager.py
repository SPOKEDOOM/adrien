from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from app.personality.personality_config import PersonalityConfig
from app.personality.personality_profile import PersonalityProfile
from app.personality.traits import TraitRegistry


class PersonalityValidationError(ValueError):
    pass


class PersonalityManager(QObject):
    personality_changed = Signal(object)
    error = Signal(str)

    def __init__(self, config: PersonalityConfig | None = None,
                 trait_registry: TraitRegistry | None = None, parent=None) -> None:
        super().__init__(parent)
        self.config = config or PersonalityConfig()
        self.trait_registry = trait_registry or TraitRegistry()
        self.profile_path = Path(self.config.profile_path) if self.config.profile_path else Path(__file__).with_name("default_profile.json")
        self.profile = self._load()

    def _load(self) -> PersonalityProfile:
        try:
            values = json.loads(self.profile_path.read_text(encoding="utf-8"))
            values.update({
                "name": self.config.name, "tone": self.config.tone,
                "verbosity": self.config.verbosity, "humor": self.config.humor,
                "honesty": self.config.honesty, "traits": self.config.default_traits,
            })
            profile = PersonalityProfile.from_mapping(values)
            self.validate(profile)
            return profile
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            raise PersonalityValidationError(f"Unable to load personality profile: {exc}") from exc

    def validate(self, profile: PersonalityProfile) -> None:
        for name in ("name", "mission", "tone", "style", "honesty", "voice"):
            if not getattr(profile, name).strip():
                raise PersonalityValidationError(f"Personality {name} cannot be empty")
        if profile.verbosity not in ("low", "medium", "high"):
            raise PersonalityValidationError("Personality verbosity must be low, medium, or high")
        if profile.humor not in ("none", "low", "medium", "high"):
            raise PersonalityValidationError("Personality humor is invalid")
        try: self.trait_registry.compose(profile.traits)
        except ValueError as exc: raise PersonalityValidationError(str(exc)) from exc

    def reload(self) -> bool:
        try:
            profile = self._load()
        except PersonalityValidationError as exc:
            self.error.emit(str(exc)); return False
        self.profile = profile
        self.personality_changed.emit(profile)
        return True
