# ---------------------------------------------------------------------------
# Recursively resolves a record ID through its `$base` prototype chain.
# and produce a fully-merged flat dictionary.
# ---------------------------------------------------------------------------
from data.registry import _get_registry, _merge

def load_record(record_id: str) -> dict:
    """Return a fully resolved record dictionary for 'record_id'"""
    registry = _get_registry()
    raw = registry.get(record_id)
    if raw is None:
        raise ValueError(f"Record not found: {record_id!r}")
    base_id: str | None = raw.get("$base")
    if base_id:
        base_resolved = load_record(base_id)
        return _merge(base_resolved, raw)
    return dict(raw)