"""Send one image to OpenAI and save editable, structured label JSON."""
import argparse
import config
from common import extract_label
from cli_support import setting, load_capture, write_json, run


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image")
    parser.add_argument("--output", default="captures/label.json")
    parser.add_argument("--model", default=config.VISION_MODEL)
    args = parser.parse_args()
    image, capture = load_capture(args.image)
    label = extract_label(image, setting("OPENAI_API_KEY", secret=True), args.model).model_dump()
    write_json(args.output, {"capture": capture, "label": label, "original_output": label,
                             "method": "openai_vision", "model": args.model})
    print(f"Saved {args.output}. Review and edit the label fields before ingestion.")
    print(f"Product: {label['product_name']} | Price: {label['price_text']} | Currency: {label['currency']}")
    for concern in label["concerns"]:
        print("Review:", concern)


if __name__ == "__main__":
    run(main)
