import json
import shutil
from pathlib import Path
import numpy as np

class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, (np.floating, np.integer)):
            return float(obj) if isinstance(obj, np.floating) else int(obj)
        return super().default(obj)


class AssetManager:
    def __init__(self, run_dir: str | Path, max_runs: int | None = 20):
        self.run_dir = Path(run_dir)
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.revision = 0
        if max_runs:
            self._cleanup_old_runs(max_runs)

    def start_revision(self) -> int:
        """Start a new revision, returns the revision number."""
        self.revision += 1
        return self.revision

    @property
    def base_path(self) -> Path:
        """Current base path (run_dir or revision subfolder)."""
        if self.revision == 0:
            return self.run_dir
        return self.run_dir / f"revision_{self.revision}"

    def stage_path(self, stage: str) -> Path:
        path = self.base_path / stage
        path.mkdir(parents=True, exist_ok=True)
        return path

    def write_text(self, stage: str, name: str, content: str) -> Path:
        path = self.stage_path(stage) / name
        path.write_text(content)
        return path

    def write_json(self, stage: str, name: str, payload: object) -> Path:
        text = json.dumps(payload, indent=2, cls=NumpyEncoder)
        return self.write_text(stage, name, text)

    def write_bytes(self, stage: str, name: str, data: bytes) -> Path:
        path = self.stage_path(stage) / name
        path.write_bytes(data)
        return path

    def _cleanup_old_runs(self, max_runs: int):
        runs_dir = self.run_dir.parent
        if not runs_dir.exists():
            return
        runs = sorted(runs_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
        for old_run in runs[max_runs:]:
            shutil.rmtree(old_run, ignore_errors=True)
