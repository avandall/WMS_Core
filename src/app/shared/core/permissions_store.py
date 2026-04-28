"""Persistence for per-user permission overrides."""
from __future__ import annotations
import json
import os
from typing import Dict, List, Set
from .permissions import Permission

STORE_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "permissions_overrides.json")


def _ensure_store_dir() -> None:
    dir_path = os.path.dirname(STORE_PATH)
    if not os.path.exists(dir_path):
        os.makedirs(dir_path, exist_ok=True)


def load_overrides() -> Dict[str, List[str]]:
    _ensure_store_dir()
    if not os.path.exists(STORE_PATH):
        return {}
    try:
        with open(STORE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_overrides(data: Dict[str, List[str]]) -> None:
    _ensure_store_dir()
    with open(STORE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def get_user_overrides(user_id: int) -> Set[Permission]:
    data = load_overrides()
    perms = data.get(str(user_id), [])
    out: Set[Permission] = set()
    for p in perms:
        try:
            out.add(Permission(p))
        except Exception:
            pass
    return out


def set_user_overrides(user_id: int, permissions: List[str]) -> None:
    data = load_overrides()
    data[str(user_id)] = permissions
    save_overrides(data)


def clear_user_overrides(user_id: int) -> None:
    data = load_overrides()
    if str(user_id) in data:
        del data[str(user_id)]
        save_overrides(data)
