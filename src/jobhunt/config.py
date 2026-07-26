import yaml

REQUIRED_FIELDS = {
    "greenhouse_board": ["board"],
    "page_watch": ["url", "extract_regex"],
}


def load_config(path="config.yaml"):
    with open(path) as f:
        data = yaml.safe_load(f) or {}

    sources = data.get("sources", [])
    seen_ids = set()
    for src in sources:
        if "id" not in src or "type" not in src:
            raise ValueError(f"source is missing 'id' or 'type': {src}")
        if src["id"] in seen_ids:
            raise ValueError(f"duplicate source id: {src['id']!r}")
        seen_ids.add(src["id"])

        missing = [f for f in REQUIRED_FIELDS.get(src["type"], []) if f not in src]
        if missing:
            raise ValueError(f"source {src['id']!r} missing required fields: {missing}")

    return sources
