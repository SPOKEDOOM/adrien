from __future__ import annotations


class HybridRouter:
    MODES = ("local_only", "groq_only", "openai_only", "local_first", "groq_first", "openai_first", "automatic",
             "placeholder_only", "cloud_only", "cloud_first")

    def route(self, request, config) -> tuple[str, ...]:
        mode = config.hybrid_mode
        if mode not in self.MODES: raise ValueError(f"Unknown hybrid mode: {mode}")
        privacy = str(request.metadata.get("privacy_level", config.default_privacy_level))
        cloud_allowed = (request.allow_cloud and config.allow_cloud_ai and
                         config.cloud_backend_enabled and config.internet_available)
        local_allowed = request.allow_local and config.local_backend_enabled
        if privacy in ("local_only", "private") and not request.metadata.get("cloud_approved", False):
            cloud_allowed = False
        preferred = request.preferred_backend
        priority = list(getattr(config, "provider_priority", ("groq", "openai", "local", "placeholder")))
        configured_default = getattr(config, "default_backend", "auto")
        if preferred not in ("", "auto"):
            order = [preferred]
        elif mode == "automatic" and configured_default not in ("", "auto", "automatic"):
            order = [configured_default] + [name for name in priority if name != configured_default]
        elif mode == "local_only": order = ["local"]
        elif mode == "groq_only": order = ["groq"]
        elif mode in ("openai_only", "cloud_only"): order = ["openai"]
        elif mode == "groq_first": order = ["groq", "openai", "local"]
        elif mode in ("openai_first", "cloud_first"): order = ["openai", "groq", "local"]
        elif mode == "placeholder_only": order = ["placeholder"]
        elif mode == "automatic":
            order = priority
        else: order = ["local", "groq", "openai"]
        filtered = []
        for name in order:
            if name == "local" and not local_allowed: continue
            if name in ("openai", "groq") and not cloud_allowed: continue
            if name not in filtered: filtered.append(name)
        if config.fallback_enabled and config.placeholder_backend_enabled and "placeholder" not in filtered:
            filtered.append(config.fallback_backend)
        return tuple(filtered)
