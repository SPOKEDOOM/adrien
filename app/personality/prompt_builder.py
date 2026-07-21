from __future__ import annotations

from app.personality.traits import TraitRegistry


class PromptBuilder:
    def __init__(self, trait_registry: TraitRegistry | None = None) -> None:
        self.trait_registry = trait_registry or TraitRegistry()

    def build_prompt(self, profile, context=None, configuration=None,
                     task_instructions: str = "") -> str:
        traits = self.trait_registry.compose(profile.traits)
        lines = [
            f"Identity: You are {profile.name}.",
            f"Mission: {profile.mission}",
            f"Tone: {profile.tone}.",
            f"Response style: {profile.style}",
            f"Honesty: {profile.honesty}. Never invent facts; clearly admit uncertainty.",
            f"Humor: {profile.humor}.",
            f"Voice: {profile.voice}.",
            f"Verbosity: {profile.verbosity}. Temperature: {profile.temperature}.",
            "Active traits:",
        ]
        lines.extend(f"- {trait.name}: {trait.instruction}" for trait in traits)
        if configuration:
            lines.append(f"Current configuration: {configuration}")
        if context and context.exchanges:
            lines.append(f"Conversation continuity: {len(context.exchanges)} recent exchanges are available.")
        summary = getattr(context, "summary", None) if context else None
        if summary and summary.text:
            lines.append("Conversation summary (older context):")
            lines.append(summary.text)
        if task_instructions.strip():
            lines.append(f"Task instructions: {task_instructions.strip()}")
        return "\n".join(lines)
