"""Vault tools — read context + diff-only proposals + gated commit.

Read tools surface the Obsidian vault as context (search, read, recent
meetings per BU/project). propose_* return a unified diff WITHOUT writing.
commit_writes applies approved diffs (effecting; Meetings view only — never
invoked from Mail). The vault is git-backed, so writes are reviewable/undoable.

Reuses the existing ~/Repos/obsidian/.sync/*.py philosophy; here we read/propose
directly against the vault tree rather than re-running the whole sync.
"""
from __future__ import annotations

import difflib
import subprocess
from pathlib import Path
from typing import Any

from sacopilot.backend import config

MN = "Meeting Notes"


def _safe(rel: str) -> Path:
    """Resolve a vault-relative path, refusing escapes outside the vault."""
    p = (config.VAULT_ROOT / rel).resolve()
    if not str(p).startswith(str(config.VAULT_ROOT.resolve())):
        raise ValueError("path escapes vault")
    return p


def vault_search(query: str, max_results: int = 20) -> list[dict[str, Any]]:
    """Case-insensitive substring search over vault markdown (filename + body)."""
    q = query.lower()
    hits = []
    for p in config.VAULT_ROOT.rglob("*.md"):
        try:
            text = p.read_text(encoding="utf-8")
        except Exception:
            continue
        rel = p.relative_to(config.VAULT_ROOT).as_posix()
        if q in rel.lower() or q in text.lower():
            idx = text.lower().find(q)
            snippet = text[max(0, idx - 60): idx + 100].replace("\n", " ") if idx >= 0 else ""
            hits.append({"path": rel, "snippet": snippet})
            if len(hits) >= max_results:
                break
    return hits


def vault_read(rel_path: str) -> dict[str, Any]:
    """Read a vault note by vault-relative path."""
    p = _safe(rel_path)
    if not p.exists():
        return {"path": rel_path, "error": "not found"}
    return {"path": rel_path, "content": p.read_text(encoding="utf-8")}


def vault_recent_meetings(bu: str, limit: int = 8) -> list[dict[str, Any]]:
    """Most recent meeting notes for a BU (by filename date prefix, newest first)."""
    base = config.VAULT_ROOT / "01_Bosch" / bu / MN
    if not base.exists():
        return []
    files = sorted(base.rglob("*.md"), key=lambda p: p.name, reverse=True)
    out = []
    for p in files[:limit]:
        out.append({
            "path": p.relative_to(config.VAULT_ROOT).as_posix(),
            "title": p.stem,
        })
    return out


def _diff(rel_path: str, new_content: str) -> dict[str, Any]:
    p = _safe(rel_path)
    old = p.read_text(encoding="utf-8") if p.exists() else ""
    diff = "".join(difflib.unified_diff(
        old.splitlines(keepends=True), new_content.splitlines(keepends=True),
        fromfile=f"a/{rel_path}", tofile=f"b/{rel_path}",
    ))
    return {"path": rel_path, "diff": diff, "new_content": new_content, "is_new": not p.exists()}


def propose_meeting_note(bu: str, filename: str, content: str,
                         project: str | None = None) -> dict[str, Any]:
    """Propose a new/updated meeting note. Returns a diff; does NOT write."""
    sub = f"{MN}/{project}" if project else MN
    rel = f"01_Bosch/{bu}/{sub}/{filename}"
    if not rel.endswith(".md"):
        rel += ".md"
    return _diff(rel, content)


def propose_contact_update(bu: str, name: str, content: str) -> dict[str, Any]:
    """Propose a new/updated contact note. Returns a diff; does NOT write."""
    rel = f"01_Bosch/{bu}/Contacts/{name}.md"
    return _diff(rel, content)


def propose_project_update(bu: str, project: str, content: str) -> dict[str, Any]:
    """Propose a new/updated project/context note. Returns a diff; does NOT write."""
    rel = f"01_Bosch/{bu}/Context/{project}.md"
    return _diff(rel, content)


def commit_writes(diffs: list[dict[str, Any]]) -> dict[str, Any]:
    """Apply approved proposals to the vault. EFFECTING — Meetings view only.

    Each diff item carries {path, new_content}. Writes files; the vault git repo
    makes this reviewable/undoable.
    """
    written = []
    for d in diffs:
        rel, content = d["path"], d["new_content"]
        p = _safe(rel)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        written.append(rel)
    return {"written": written}


def vault_git_status() -> str:
    """Porcelain git status of the vault (to show what a commit changed)."""
    try:
        out = subprocess.run(
            ["git", "-C", str(config.VAULT_REPO), "status", "--short"],
            capture_output=True, text=True, timeout=15,
        )
        return out.stdout
    except Exception as e:  # noqa: BLE001
        return f"(git status unavailable: {e})"
