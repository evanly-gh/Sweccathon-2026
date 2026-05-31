"""
Save a Mesocosm run export and register it in the showcase manifest.

Usage:
    python save_run.py RUN_ID                    # auto-names by model
    python save_run.py RUN_ID --label "Claude v1" # custom label

This:
  1. Runs: mesocosm run export RUN_ID -o showcase/data/run_RUNID.json
  2. Adds an entry to showcase/data/manifest.json
  3. Copies it to showcase/data/replay.json (so the showcase still has a default)

Then just: git add showcase/data/ && git commit && git push
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

SHOWCASE_DATA = Path(__file__).parent / "showcase" / "data"
MANIFEST_PATH = SHOWCASE_DATA / "manifest.json"


def main() -> None:
    parser = argparse.ArgumentParser(description="Save a Mesocosm run for the showcase.")
    parser.add_argument("run_id", help="Mesocosm run ID")
    parser.add_argument("--label", default=None, help="Display label (default: auto from model name)")
    args = parser.parse_args()

    run_id = args.run_id
    short_id = run_id[:8]
    filename = f"run_{short_id}.json"
    filepath = SHOWCASE_DATA / filename

    # Export
    print(f"Exporting run {run_id}...")
    result = subprocess.run(
        ["mesocosm", "run", "export", run_id, "-o", str(filepath)],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        # Try with full path on Windows
        import shutil
        meso = shutil.which("mesocosm")
        if meso:
            result = subprocess.run(
                [meso, "run", "export", run_id, "-o", str(filepath)],
                capture_output=True, text=True
            )
    if result.returncode != 0:
        print(f"Export failed: {result.stderr}")
        sys.exit(1)

    print(f"Saved to {filepath}")

    # Read the export to extract metadata
    data = json.loads(filepath.read_text(encoding="utf-8"))
    model = data.get("run", {}).get("config", {}).get("agent_config", {}).get("model", "unknown")
    scores = data.get("run", {}).get("scores", {})
    episodes = len(data.get("episodes", []))
    label = args.label or f"{model} ({episodes} ep)"

    # Update manifest
    if MANIFEST_PATH.exists():
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    else:
        manifest = []

    # Remove existing entry for same run_id if re-exporting
    manifest = [e for e in manifest if e.get("run_id") != run_id]

    manifest.append({
        "run_id": run_id,
        "label": label,
        "model": model,
        "filename": filename,
        "episodes": episodes,
        "scores": scores,
    })

    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Manifest updated: {len(manifest)} runs total")

    # Also copy as replay.json (default)
    import shutil
    shutil.copy2(filepath, SHOWCASE_DATA / "replay.json")
    print(f"Copied to replay.json (default)")

    print(f"\nNext: git add showcase/data/ && git commit -m 'Add {label} run' && git push origin main")


if __name__ == "__main__":
    main()
