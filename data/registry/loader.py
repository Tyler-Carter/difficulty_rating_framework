import yaml
from data import BASE_FILES_DIR

_record_registry: dict[str, dict] | None = None

# ---------------------------------------------------------------------------
# YAML loading with !append tag support and $base prototype chain resolution
# ---------------------------------------------------------------------------
class _AppendLoader(yaml.SafeLoader):
    """SafeLoader extended to silently unwrap !append tags."""


def _append_constructor(loader: yaml.SafeLoader, node: yaml.Node) -> object:
    if isinstance(node, yaml.MappingNode):
        return loader.construct_mapping(node)
    if isinstance(node, yaml.SequenceNode):
        return loader.construct_sequence(node)
    return loader.construct_scalar(node)  # type: ignore[arg-type]


_AppendLoader.add_constructor("!append", _append_constructor)


# ---------------------------------------------------------------------------
# Private function that builds the registry from all of the .yml files
# ---------------------------------------------------------------------------
def _build_registry() -> dict[str, dict]:
    """Load every YAML file under base_files/ and return {record_id: raw_dict}."""
    registry: dict[str, dict] = {}
    search_dirs = [
        BASE_FILES_DIR / "records" / "npcs",
        BASE_FILES_DIR / "records" / "player",
        BASE_FILES_DIR / "records" / "weapons",
        BASE_FILES_DIR / "prototypes" / "npcs",
        BASE_FILES_DIR / "prototypes" / "characters",
        BASE_FILES_DIR / "prototypes" / "weapons",
    ]
    for directory in search_dirs:
        if not directory.exists():
            continue
        for path in sorted(directory.glob("*.yml")) + sorted(directory.glob("*.yaml")):
            try:
                with open(path, encoding="utf-8", errors="replace") as fh:
                    data = yaml.load(fh, Loader=_AppendLoader)
            except Exception:
                continue
            if not isinstance(data, dict):
                continue
            for record_id, record_data in data.items():
                if isinstance(record_data, dict):
                    registry[record_id] = record_data
    return registry

# ---------------------------------------------------------------------------
# Private function used to retrieve or build the record registry
# ---------------------------------------------------------------------------
def _get_registry() -> dict[str, dict] | None:
    global _record_registry
    if _record_registry is None:
        _record_registry = _build_registry()
    return _record_registry


# ---------------------------------------------------------------------------
# Private function that strips $base and $type keys from leaf before merging
# ---------------------------------------------------------------------------
def _merge(base: dict, leaf: dict) -> dict:
    """Merge a fully-resolved base record with a leaf record.

    Leaf values win over base values.  Special cases:
    - skills: merged by skill name; leaf entries overwrite base entries.
    - attributes / derivedStats: dicts are merged shallowly (leaf wins per key).
    """
    result = dict(base)
    for key, val in leaf.items():
        if key in ("$base", "$type"):
            continue
        if key == "skills" and val is not None:
            base_skills: dict[str, int] = {
                s["skill"]: s["rank"]
                for s in (result.get("skills") or [])
                if isinstance(s, dict) and "skill" in s
            }
            for entry in (val or []):
                if isinstance(entry, dict) and "skill" in entry:
                    base_skills[entry["skill"]] = entry["rank"]
            result["skills"] = [{"skill": sk, "rank": rk} for sk, rk in base_skills.items()]
        elif key in ("attributes", "derivedStats") and isinstance(val, dict):
            merged_sub = dict(result.get(key) or {})
            merged_sub.update({k: v for k, v in val.items() if v is not None})
            result[key] = merged_sub
        else:
            result[key] = val
    return result
