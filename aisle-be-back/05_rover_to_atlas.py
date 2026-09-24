"""Full loop: capture -> extract -> pause for review -> save to Atlas."""
import argparse
import asyncio
import json
from pathlib import Path
import config
from common import viam_action, extract_label, build_document, save_observation
from cli_support import setting, new_capture, write_json, run


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="captures/live.jpg")
    args = parser.parse_args()
    raw = asyncio.run(viam_action(setting("VIAM_ADDRESS"), setting("VIAM_API_KEY_ID"),
                                 setting("VIAM_API_KEY", secret=True), config.CAMERA_NAME))
    image, capture = new_capture(raw, args.output, "Viam camera")
    label = extract_label(image, setting("OPENAI_API_KEY", secret=True), config.VISION_MODEL).model_dump()
    review_path = Path(args.output).with_suffix(".label.json")
    write_json(review_path, {"capture": capture, "label": label, "original_output": label,
                            "method": "openai_vision", "model": config.VISION_MODEL})
    print(json.dumps(label, indent=2))
    print(f"Open {args.output} and {review_path}. Edit label fields if needed, including USD currency.")
    if input("Type SAVE after reviewing, or anything else to keep files without saving: ").strip() != "SAVE":
        print("Files retained; nothing written to Atlas.")
        return
    payload = json.loads(review_path.read_text())
    # Protect source metadata from accidental edits during review.
    if payload["capture"] != capture:
        raise ValueError("Capture metadata changed during review. Only edit label fields.")
    doc = build_document(payload, Path(args.output).read_bytes())
    inserted = save_observation(setting("ATLAS_URI", secret=True), config.DATABASE, doc)
    print("Saved to Atlas." if inserted else "Already saved; no duplicate created.")


if __name__ == "__main__":
    run(main)
