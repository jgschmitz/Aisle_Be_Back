"""Offline: create a sample photo and editable label JSON. No API keys required."""
import argparse
from pathlib import Path
from PIL import Image, ImageDraw
import io
from cli_support import new_capture, write_json, run
from common import money_to_cents


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="captures/sample.jpg")
    parser.add_argument("--price", default="4.99", help="Synthetic USD single-item price")
    args = parser.parse_args()
    price = f"{money_to_cents(args.price) / 100:.2f}"
    image = Image.new("RGB", (1100, 550), "#fffaf0")
    draw = ImageDraw.Draw(image)
    draw.rectangle((20, 20, 1080, 530), outline="#00684a", width=8)
    draw.text((60, 65), "DEMO LABEL - Ridiculously Crunchy Chips", font_size=36, fill="black")
    draw.text((60, 155), "8 oz | SKU: CHIPS-001", font_size=40, fill="black")
    draw.text((60, 270), f"USD ${price}", font_size=110, fill="black")
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    _, capture = new_capture(buf.getvalue(), args.output, "Sample label")
    label = {"product_name": "Ridiculously Crunchy Chips", "size_text": "8 oz",
             "sku": "CHIPS-001", "barcode": None, "price_text": price, "currency": "USD",
             "promotion_text": None, "raw_label_text": f"DEMO LABEL Ridiculously Crunchy Chips 8 oz SKU: CHIPS-001 USD ${price}",
             "concerns": []}
    output = str(Path(args.output).with_suffix(".label.json"))
    write_json(output, {"capture": capture, "label": label, "method": "manual", "model": None})
    print(f"Created {args.output} and {output}. Synthetic demo data; no AI call made.")


if __name__ == "__main__":
    run(main)
