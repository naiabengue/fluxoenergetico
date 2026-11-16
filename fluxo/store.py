"""Armazenamento em ficheiros de texto versionados (JSON Lines + Markdown)."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

import yaml

from .dedup import canonical_url
from .models import Item


def item_id(url: str) -> str:
    return hashlib.sha1(canonical_url(url).encode("utf-8")).hexdigest()[:16]


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def split_front_matter(text: str) -> tuple[dict[str, Any], str]:
    if text.startswith("---"):
        _, fm, body = text.split("---", 2)
        return yaml.safe_load(fm) or {}, body.lstrip("\n")
    return {}, text


class Store:
    def __init__(self, root: Path | str):
        self.root = Path(root)
        self.data = self.root / "data"
        self.seen_path = self.data / "state" / "seen.json"
        self._seen: set[str] | None = None

    # ---- itens recolhidos -------------------------------------------------
    @property
    def seen(self) -> set[str]:
        if self._seen is None:
            self._seen = set(json.loads(self.seen_path.read_text())) if self.seen_path.exists() else set()
        return self._seen

    def _save_seen(self) -> None:
        self.seen_path.parent.mkdir(parents=True, exist_ok=True)
        self.seen_path.write_text(json.dumps(sorted(self.seen)), encoding="utf-8")

    def add_items(self, items: Iterable[Item]) -> tuple[int, int]:
        """Guarda itens novos; devolve (novos, duplicados)."""
        new, dup = 0, 0
        by_month: dict[str, list[Item]] = {}
        for it in items:
            it.id = item_id(it.url)
            if it.id in self.seen:
                dup += 1
                continue
            self.seen.add(it.id)
            month = (it.collected_at or datetime.now(timezone.utc).isoformat())[:7]
            by_month.setdefault(month, []).append(it)
            new += 1
        for month, its in by_month.items():
            path = self.data / "items" / f"{month}.jsonl"
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as fh:
                for it in its:
                    fh.write(json.dumps(it.to_dict(), ensure_ascii=False) + "\n")
        if new:
            self._save_seen()
        return new, dup

    def recent_items(self, days: int, now: datetime | None = None) -> list[Item]:
        now = now or datetime.now(timezone.utc)
        since = now - timedelta(days=days)
        out: list[Item] = []
        folder = self.data / "items"
        if not folder.exists():
            return out
        for path in sorted(folder.glob("*.jsonl"))[-3:]:
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                it = Item.from_dict(json.loads(line))
                ts = parse_iso(it.collected_at)
                if ts and ts >= since:
                    out.append(it)
        return out

    # ---- itens já tratados (não voltam a ser redigidos) ---------------------
    def _state(self, name: str) -> dict[str, Any]:
        path = self.data / "state" / f"{name}.json"
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}

    def _save_state(self, name: str, data: dict[str, Any]) -> None:
        path = self.data / "state" / f"{name}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")

    def processed(self) -> dict[str, Any]:
        return self._state("processed")

    def mark_processed(self, item_id: str, decision: str, when: str) -> None:
        data = self.processed()
        data[item_id] = {"decision": decision, "date": when[:10]}
        self._save_state("processed", data)

    def instagram_state(self) -> dict[str, Any]:
        return self._state("instagram")

    def save_instagram_state(self, data: dict[str, Any]) -> None:
        self._save_state("instagram", data)

    def log_rejected(self, record: dict[str, Any]) -> None:
        month = str(record.get("date", datetime.now(timezone.utc).isoformat()))[:7]
        path = self.data / "rejected" / f"{month}.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")

    # ---- registo de execuções --------------------------------------------
    def log_run(self, record: dict[str, Any]) -> None:
        month = str(record.get("started", datetime.now(timezone.utc).isoformat()))[:7]
        path = self.data / "runs" / f"{month}.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")

    def runs(self, limit: int = 30) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        folder = self.data / "runs"
        for path in sorted(folder.glob("*.jsonl")) if folder.exists() else []:
            out += [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
        return out[-limit:]

    # ---- artigos publicados ------------------------------------------------
    def published_articles(self) -> list[dict[str, Any]]:
        arts: list[dict[str, Any]] = []
        folder = self.root / "content" / "articles"
        for path in sorted(folder.rglob("*.md")) if folder.exists() else []:
            meta, body = split_front_matter(path.read_text(encoding="utf-8"))
            meta["body"] = body
            meta["path"] = str(path.relative_to(self.root))
            arts.append(meta)
        arts.sort(key=lambda a: str(a.get("date", "")), reverse=True)
        return arts
