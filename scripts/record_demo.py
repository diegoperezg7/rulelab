"""Copy a finished `rulelab run` into examples/demo/results.json and label it as recorded.

Only adds a "recorded" block (date, version, hardware, model, command). Never touches the runs.

    uv run python scripts/record_demo.py path/to/results.json "<exact command used>"
"""

import json
import sys
from pathlib import Path

src, command = Path(sys.argv[1]), sys.argv[2]
data = json.loads(src.read_text(encoding="utf-8"))
if data.get("status") != "complete":
    sys.exit(f"refusing to record a run with status {data.get('status')!r}")
data["recorded"] = {
    "date": data["created"][:10],
    "version": data["version"],
    "hardware": data["meta"].get("hardware", data["meta"].get("platform", "")),
    "model": data["model"],
    "command": command,
}
out = Path(__file__).resolve().parents[1] / "examples" / "demo" / "results.json"
out.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
print(f"wrote {out}")
