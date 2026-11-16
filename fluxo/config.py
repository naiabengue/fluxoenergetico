from __future__ import annotations

from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any

import yaml

from .models import Source


@dataclass
class Config:
    root: Path
    site: dict[str, Any]
    editorial: dict[str, Any]
    sources: list[Source]

    def source(self, source_id: str) -> Source:
        for s in self.sources:
            if s.id == source_id:
                return s
        raise KeyError(source_id)


def _read_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def _make_source(raw: dict[str, Any], defaults: dict[str, Any]) -> Source:
    data = {**defaults, **raw}
    data["bee_number"] = data.pop("bee", None)
    allowed = {f.name for f in fields(Source)}
    return Source(**{k: v for k, v in data.items() if k in allowed})


def load_config(root: Path | str) -> Config:
    root = Path(root)
    cfg_dir = root / "config"
    raw_sources = _read_yaml(cfg_dir / "sources.yaml")
    defaults = raw_sources.get("defaults", {})
    sources = [_make_source(s, defaults) for s in raw_sources.get("sources", [])]
    ids = [s.id for s in sources]
    dupes = {i for i in ids if ids.count(i) > 1}
    if dupes:
        raise ValueError(f"ids de fonte repetidos: {sorted(dupes)}")
    return Config(root=root,
                  site=_read_yaml(cfg_dir / "site.yaml"),
                  editorial=_read_yaml(cfg_dir / "editorial.yaml"),
                  sources=sources)
