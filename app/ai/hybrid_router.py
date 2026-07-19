from __future__ import annotations


class HybridRouter:
    MODES = ("local_only", "cloud_only", "local_first", "cloud_first", "automatic", "placeholder_only")

    def route(self, request, config) -> tuple[str, ...]:
        mode = config.hybrid_mode
        if mode not in self.MODES: raise ValueError(f"Unknown hybrid mode: {mode}")
        privacy = str(request.metadata.get("privacy_level", config.default_privacy_level))
        cloud_allowed = request.allow_cloud and config.cloud_backend_enabled and config.internet_available
        local_allowed = request.allow_local and config.local_backend_enabled
        if privacy in ("local_only", "private") and not request.metadata.get("cloud_approved", False):
            cloud_allowed = False
        preferred = request.preferred_backend
        if preferred not in ("", "auto"):
            order = [preferred]
        elif mode == "local_only": order = ["local"]
        elif mode == "cloud_only": order = ["openai"]
        elif mode == "cloud_first": order = ["openai", "local"]
        elif mode == "placeholder_only": order = ["placeholder"]
        elif mode == "automatic" and request.metadata.get("high_quality_reasoning"):
            order = ["openai", "local"]
        else: order = ["local", "openai"]
        filtered = []
        for name in order:
            if name == "local" and not local_allowed: continue
            if name == "openai" and not cloud_allowed: continue
            if name not in filtered: filtered.append(name)
        if config.fallback_enabled and config.placeholder_backend_enabled and "placeholder" not in filtered:
            filtered.append(config.fallback_backend)
        return tuple(filtered)
