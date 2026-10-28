"""Write the guide JSON Schema to schema/guide.schema.json (used by the frontend)."""

import json
import sys
from pathlib import Path

from app.schema import Guide

OUT = Path(__file__).resolve().parents[2] / "schema" / "guide.schema.json"


def render() -> str:
    return json.dumps(Guide.model_json_schema(), indent=2, sort_keys=True) + "\n"


if __name__ == "__main__":
    if "--check" in sys.argv:
        if not OUT.exists() or OUT.read_text() != render():
            print("schema/guide.schema.json is out of date; run scripts/export_schema.py")
            sys.exit(1)
    else:
        OUT.write_text(render())
        print(f"wrote {OUT}")
