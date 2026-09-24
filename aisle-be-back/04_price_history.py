"""Show observations for one exact SKU and store, and consecutive price changes."""
import argparse
import config
from common import mongo_client
from cli_support import setting, run


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sku", required=True)
    parser.add_argument("--store", default=config.STORE_ID)
    parser.add_argument("--include-samples", action="store_true")
    args = parser.parse_args()
    query = {"product.sku": args.sku, "location.store_id": args.store, "price.currency": "USD"}
    if not args.include_samples:
        query["capture.source"] = {"$ne": "Sample label"}
    with mongo_client(setting("ATLAS_URI", secret=True)) as client:
        rows = list(client[config.DATABASE].price_observations.find(
            query, {"capture.image_jpeg": 0}).sort("captured_at", -1).limit(100))
    if not rows:
        print("No matching observations. Sample data requires --include-samples.")
        return
    previous = None
    for row in reversed(rows):
        cents = row["price"]["amount_minor"]
        delta = "first observation" if previous is None else f"change ${(cents-previous)/100:+.2f}"
        print(f"{row['captured_at'].isoformat()} | ${cents/100:.2f} | {delta} | {row['product']['label_name']}")
        previous = cents
    print("Latest 100 observations. Matching relies on your reviewed SKU; promotional terms may differ.")


if __name__ == "__main__":
    run(main)
