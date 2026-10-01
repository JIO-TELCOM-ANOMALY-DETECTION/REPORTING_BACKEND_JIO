from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .config import Settings, settings
from .exceptions import ArtifactError, NotFoundError, ValidationError

ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
STAGES = frozenset({"part_a", "part_b", "part_c", "part_d"})


class ArtifactPathResolver:
    """The sole path-trust boundary for persisted ML artifacts."""

    def __init__(self, config: Settings = settings) -> None:
        self.config = config
        self.runs_root = config.ml_runs_root.resolve()

    @staticmethod
    def identifier(value: str, field: str) -> str:
        value = value.strip()
        if not ID_PATTERN.fullmatch(value):
            raise ValidationError(f"Invalid {field}.", error_code="INVALID_IDENTIFIER")
        return value

    def run_root(self, run_id: str) -> Path:
        run_id = self.identifier(run_id, "run_id")
        root = (self.runs_root / run_id).resolve()
        self._under(root, self.runs_root)
        if not root.is_dir():
            raise NotFoundError("Run not found.", error_code="RUN_NOT_FOUND")
        return root

    def stage(self, stage: str) -> str:
        stage = stage.strip().lower().replace("-", "_")
        if stage not in STAGES:
            raise ValidationError("Unsupported stage.", error_code="INVALID_STAGE")
        return stage

    def file(self, candidate: str | Path, *, run_root: Path, recorded_run_directory: str | None = None) -> Path:
        """Resolve a stored path under its current run, optionally remapping relocation."""
        raw = Path(candidate).expanduser()
        resolved = raw.resolve()
        if self._is_under(resolved, run_root):
            return self._existing_file(resolved)
        if recorded_run_directory:
            old_root = Path(recorded_run_directory).expanduser().resolve()
            if self._is_under(resolved, old_root):
                remapped = (run_root / resolved.relative_to(old_root)).resolve()
                self._under(remapped, run_root)
                return self._existing_file(remapped)
        raise ArtifactError("Artifact path is outside the owning run.", error_code="UNSAFE_ARTIFACT_PATH")

    def relative_name(self, path: Path, run_root: Path) -> str:
        return path.resolve().relative_to(run_root.resolve()).as_posix()

    @staticmethod
    def _is_under(path: Path, root: Path) -> bool:
        try:
            path.relative_to(root)
            return True
        except ValueError:
            return False

    def _under(self, path: Path, root: Path) -> None:
        if not self._is_under(path, root):
            raise ValidationError("Path traversal was rejected.", error_code="PATH_TRAVERSAL")

    @staticmethod
    def _existing_file(path: Path) -> Path:
        if not path.exists() or not path.is_file():
            raise ArtifactError("Referenced artifact is unavailable.", error_code="ARTIFACT_NOT_FOUND")
        return path
