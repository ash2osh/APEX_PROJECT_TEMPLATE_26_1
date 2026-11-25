"""Per-environment release state for Lean release bundles.

ASHARIF 2026-11-25: each bundle records, per environment, what the runner applied there
(releases/<slug>/state/<env>.json). Pure functions only: no database access. The runner in
scripts/release.py decides what to apply from these records and writes them after a fully
successful run. See docs/superpowers/specs/2026-11-25-release-state-design.md.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

STATE_SCHEMA_VERSION = 1
STATE_DIR = "state"
STATE_ENVIRONMENTS = ("dev", "staging", "prod")


class StateError(Exception):
    """A state file that cannot be trusted (corrupt, wrong bundle or environment)."""


def text_sha256(text: str) -> str:
    """Fingerprint of a bundle file: sha256 of its text with line endings normalised to LF."""
    normalised = text.replace("\r\n", "\n").replace("\r", "\n")
    return hashlib.sha256(normalised.encode("utf-8")).hexdigest()


def _app_dirs(repo_root: Path, app_id: int) -> list[Path]:
    apps_dir = repo_root / "apps"
    if not apps_dir.is_dir():
        return []
    found = [p for p in apps_dir.glob(f"*/{app_id}") if p.is_dir() and not p.is_symlink()]
    direct = apps_dir / str(app_id)
    if direct.is_dir() and not direct.is_symlink():
        found.append(direct)
    return sorted(found)


def app_source_sha256(repo_root: Path, app_id: int, app_dir: Path | None = None) -> str:
    """Fingerprint of an app's source tree: sorted relative paths and bytes. No source → sha256 of nothing."""
    digest = hashlib.sha256()
    dirs = [app_dir] if app_dir is not None else _app_dirs(repo_root, app_id)
    for base in dirs:
        files = sorted(
            (p for p in base.rglob("*") if p.is_file() and not p.is_symlink()),
            key=lambda p: p.relative_to(base).as_posix(),
        )
        for path in files:
            rel = path.relative_to(base).as_posix().encode("utf-8")
            data = path.read_bytes()
            digest.update(len(rel).to_bytes(8, "big") + rel)
            digest.update(len(data).to_bytes(8, "big") + data)
    return digest.hexdigest()


def state_path(bundle_dir: Path, env: str) -> Path:
    if env not in STATE_ENVIRONMENTS:
        raise ValueError(f"unknown environment for release state: {env!r}")
    return bundle_dir / STATE_DIR / f"{env}.json"


def load_state(bundle_dir: Path, slug: str, env: str) -> dict[str, Any] | None:
    """Read state/<env>.json, or None when the environment never had a successful run."""
    path = state_path(bundle_dir, env)
    label = f"releases/{slug}/{STATE_DIR}/{env}.json"
    for candidate in (path.parent, path):
        if candidate.is_symlink():
            raise StateError(f"{label}: symlinks are not allowed")
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise StateError(f"{label} is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise StateError(f"{label} must be a JSON object")
    if data.get("schemaVersion") != STATE_SCHEMA_VERSION:
        raise StateError(f"{label} schemaVersion must be {STATE_SCHEMA_VERSION}")
    if data.get("slug") != slug:
        raise StateError(f"{label} slug {data.get('slug')!r} does not match bundle {slug!r}")
    if data.get("env") != env:
        raise StateError(f"{label} env {data.get('env')!r} does not match {env!r}")
    if not isinstance(data.get("steps", {}), dict):
        raise StateError(f"{label} 'steps' must be an object")
    if not isinstance(data.get("apps", {}), dict):
        raise StateError(f"{label} 'apps' must be an object")
    return data


def write_state(bundle_dir: Path, env: str, state: Mapping[str, Any]) -> None:
    """Write state/<env>.json atomically (temp file and rename), keys sorted, LF."""
    path = state_path(bundle_dir, env)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(state, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    fd, tmp_name = tempfile.mkstemp(prefix=f".{env}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(payload)
        os.replace(tmp_name, path)
    except BaseException:
        Path(tmp_name).unlink(missing_ok=True)
        raise


def _recorded_sha(env_state: Mapping[str, Any] | None, rel_file: str) -> str | None:
    if not env_state:
        return None
    entry = (env_state.get("steps") or {}).get(rel_file)
    return entry.get("sha256") if isinstance(entry, dict) else None


def select_steps(
    current: Mapping[str, str], env_state: Mapping[str, Any] | None, *, full: bool
) -> tuple[list[str], list[str]]:
    """Split bundle files into (to apply, skipped), keeping bundle order."""
    to_apply: list[str] = []
    skipped: list[str] = []
    for rel_file, sha in current.items():
        if not full and _recorded_sha(env_state, rel_file) == sha:
            skipped.append(rel_file)
        else:
            to_apply.append(rel_file)
    return to_apply, skipped


def staging_mismatches(
    current: Mapping[str, str], app_shas: Mapping[int, str], staging_state: Mapping[str, Any] | None
) -> list[str]:
    """Bundle files and apps whose current fingerprint differs from what staging received."""
    out = [rel for rel, sha in current.items() if _recorded_sha(staging_state, rel) != sha]
    apps = (staging_state or {}).get("apps") or {}
    for app_id, sha in app_shas.items():
        entry = apps.get(str(app_id))
        if not isinstance(entry, dict) or entry.get("sourceSha256") != sha:
            out.append(f"app {app_id}")
    return out


def effective_status(
    manifest: Mapping[str, Any],
    current: Mapping[str, str],
    app_shas: Mapping[int, str],
    staging_state: Mapping[str, Any] | None,
) -> tuple[str, list[str]]:
    """Status as the files show it: draft, staged, stale (staged but changed since) or deployed."""
    status = manifest.get("status")
    if status == "deployed":
        return "deployed", []
    mismatches = staging_mismatches(current, app_shas, staging_state)
    if status == "staged":
        return ("stale", mismatches) if mismatches else ("staged", [])
    return "draft", mismatches


def merge_state(
    previous: Mapping[str, Any] | None,
    *,
    slug: str,
    env: str,
    current: Mapping[str, str],
    applied: Iterable[str],
    live_hashes: Mapping[str, str],
    app_shas_deployed: Mapping[int, str],
    run: Mapping[str, Any],
    at: str,
    commit: str,
) -> dict[str, Any]:
    """New state after a successful run: applied files updated, skipped ones kept, removed ones dropped."""
    applied_set = set(applied)
    old_steps = (previous or {}).get("steps") or {}
    steps: dict[str, Any] = {}
    for rel_file, sha in current.items():
        if rel_file in applied_set:
            entry: dict[str, Any] = {"sha256": sha, "at": at, "commit": commit}
            if rel_file in live_hashes:
                entry["liveSha256"] = live_hashes[rel_file]
            steps[rel_file] = entry
        elif isinstance(old_steps.get(rel_file), dict):
            steps[rel_file] = dict(old_steps[rel_file])
    apps = {k: dict(v) for k, v in ((previous or {}).get("apps") or {}).items() if isinstance(v, dict)}
    for app_id, sha in app_shas_deployed.items():
        apps[str(app_id)] = {"sourceSha256": sha, "at": at}
    return {
        "schemaVersion": STATE_SCHEMA_VERSION,
        "slug": slug,
        "env": env,
        "lastRun": dict(run),
        "steps": steps,
        "apps": apps,
    }
