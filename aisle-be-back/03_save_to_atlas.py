"""Save a reviewed label plus its JPEG in Atlas. Repeating a scan is idempotent."""
import argparse
import json
from pathlib import Path
import config
from common import build_document, save_observation
from cli_support import setting, run


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("label_json")
    parser.add_argument("image", help="Exact normalized JPEG associated with this extraction")
    parser.add_argument("--reviewed", action="store_true", help="Confirm you checked product and USD single-item price")
    args = parser.parse_args()
    if not args.reviewed:
        parser.error("Review the label JSON against the image, then pass --reviewed.")
    payload = json.loads(Path(args.label_json).read_text())
    doc = build_document(payload, Path(args.image).read_bytes())
    inserted = save_observation(setting("ATLAS_URI", secret=True), config.DATABASE, doc)
    print("Saved to Atlas." if inserted else "Already saved; existing observation preserved.")
    print("Scan ID:", doc["scan_id"])


if __name__ == "__main__":
    run(main)
