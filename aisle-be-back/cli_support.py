"""Small file and prompt helpers; credentials are never written to output files."""
import hashlib
import json
from datetime import datetime, timezone
from getpass import getpass
from pathlib import Path
import uuid
import config
from common import jpeg_bytes


def setting(name, secret=False):
    value = getattr(config, name, "")
    if value:
        return value
    value = (getpass if secret else input)(f"{name}: ").strip()
    if not value:
        raise ValueError(f"{name} is required.")
    return value


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def new_capture(raw, output, source):
    path = Path(output).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    image = jpeg_bytes(raw)
    path.write_bytes(image)
    capture = {
        "scan_id": str(uuid.uuid4()), "captured_at": datetime.now(timezone.utc).isoformat(),
        "source": source, "robot_id": config.ROBOT_ID,
        "location": {"store_id": config.STORE_ID, "aisle": config.AISLE, "shelf": config.SHELF},
        "sha256": hashlib.sha256(image).hexdigest(),
    }
    write_json(str(path) + ".capture.json", capture)
    return image, capture


def load_capture(path):
    path = Path(path).resolve()
    sidecar = Path(str(path) + ".capture.json")
    if sidecar.exists():
        image = path.read_bytes()
        capture = json.loads(sidecar.read_text())
        if hashlib.sha256(image).hexdigest() != capture["sha256"]:
            raise ValueError("Image differs from its capture metadata; use a new image path.")
        return image, capture
    # External photos are normalized into a separate file; never overwrite originals.
    normalized = path.with_name(path.stem + ".normalized.jpg")
    return new_capture(path.read_bytes(), normalized, "Upload image")


def run(main):
    try:
        main()
    except KeyboardInterrupt:
        raise SystemExit("Cancelled.")
    except Exception as exc:
        # SDK exceptions may contain connection data. Keep terminal errors credential-free.
        if isinstance(exc, (ValueError, FileNotFoundError)):
            raise SystemExit(str(exc)) from None
        raise SystemExit(f"{type(exc).__name__}: operation failed. Check credentials, network access, and configuration.") from None
