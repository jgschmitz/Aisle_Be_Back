"""Connect to Viam; list cameras or capture one JPEG. Does not move the rover."""
import argparse
import asyncio
import config
from common import viam_action
from cli_support import setting, new_capture, run


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true", help="List configured camera names")
    parser.add_argument("--camera", default=config.CAMERA_NAME)
    parser.add_argument("--output", default="captures/shelf.jpg")
    args = parser.parse_args()
    result = asyncio.run(viam_action(setting("VIAM_ADDRESS"), setting("VIAM_API_KEY_ID"),
                                    setting("VIAM_API_KEY", secret=True), None if args.list else args.camera))
    if args.list:
        print("Cameras:", ", ".join(result) or "none")
    else:
        _, capture = new_capture(result, args.output, "Viam camera")
        print(f"Saved {args.output}; scan {capture['scan_id']}")


if __name__ == "__main__":
    run(main)
