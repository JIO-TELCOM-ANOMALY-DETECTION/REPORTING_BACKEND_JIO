from __future__ import annotations

from typing import Any
from app.core.path_resolver import ArtifactPathResolver
from app.core.exceptions import ArtifactError, NotFoundError
from .common import read_json


class ManifestReader:
    def __init__(self, resolver: ArtifactPathResolver) -> None:
        self.resolver = resolver

    def load(self, run_id: str) -> tuple[dict[str, Any], object]:
        root = self.resolver.run_root(run_id)
        manifest = read_json(self.resolver.file(root / "manifest.json", run_root=root), self.resolver.config.default_file_encoding)
        if manifest.get("manifest_version") != "2.0":
            raise ArtifactError("Unsupported manifest version.", error_code="UNSUPPORTED_MANIFEST_VERSION")
        if manifest.get("run_id") != run_id:
            raise ArtifactError("Manifest run identity is inconsistent.", error_code="MANIFEST_RUN_ID_MISMATCH")
        return manifest, root

    @staticmethod
    def attempt(manifest: dict[str, Any], attempt_id: str) -> dict[str, Any]:
        attempts = manifest.get("attempts")
        attempt = attempts.get(attempt_id) if isinstance(attempts, dict) else None
        if not isinstance(attempt, dict):
            raise NotFoundError("Attempt not found.", error_code="ATTEMPT_NOT_FOUND")
        return attempt
