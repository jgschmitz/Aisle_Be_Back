"""Aisle Be Back: streamlit run streamlit_app.py (Python 3.11+)."""
from __future__ import annotations

import asyncio
import base64
import hashlib
import io
import re
import uuid
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from PIL import Image, ImageDraw, ImageOps
from pydantic import BaseModel
import streamlit as st

from config import (ATLAS_URI, OPENAI_API_KEY, VIAM_ADDRESS, VIAM_API_KEY_ID,
                    VIAM_API_KEY, CAMERA_NAME, VISION_MODEL as DEFAULT_MODEL)


from common import Label, money_to_cents, jpeg_bytes, viam_action, extract_label, mongo_client, save_observation


def new_capture(raw, source, robot_id, location):
    normalized = jpeg_bytes(raw)
    st.session_state.capture = {
        "id": str(uuid.uuid4()), "image": normalized,
        "captured_at": datetime.now(timezone.utc), "source": source,
        "robot_id": robot_id, "location": dict(location),
    }
    st.session_state.label = None
    st.session_state.saved = False
    st.session_state.extraction_model = None
    st.session_state.revision = 0


def show_error(exc, secrets=()):
    message = str(exc)
    for secret in secrets:
        if secret:
            message = message.replace(secret, "[redacted]")
    message = re.sub(r"mongodb(?:\+srv)?://\S+", "[redacted MongoDB URI]", message)
    st.error(f"{type(exc).__name__}: {message[:600]}")


def sample_image():
    image = Image.new("RGB", (1100, 550), "#fffaf0")
    draw = ImageDraw.Draw(image)
    draw.rectangle((25, 25, 1075, 525), outline="#142b22", width=8)
    draw.text((60, 60), "DEMO SHELF LABEL", fill="#00684a", font_size=36)
    draw.text((60, 140), "Ridiculously Crunchy Chips", fill="#111111", font_size=48)
    draw.text((60, 215), "8 oz  |  SKU: CHIPS-001", fill="#222222", font_size=30)
    draw.text((60, 300), "USD $4.99", fill="#111111", font_size=92)
    out = io.BytesIO()
    image.save(out, format="PNG")
    return out.getvalue()


def main():
    st.set_page_config(page_title="Aisle Be Back", page_icon="🛒", layout="wide")
    st.markdown("""<style>
    .stApp {background:linear-gradient(135deg,#120e23,#201332);color:#f4efff}
    [data-testid="stSidebar"] {background:#171124}
    .stButton>button[kind="primary"] {background:#00ed64;color:#062b1c;border:0}
    h1,h2,h3 {color:#e4d5ff!important}
    </style>""", unsafe_allow_html=True)
    st.title("🛒 Aisle Be Back")
    st.caption("A little rover. A shelf full of prices. Atlas remembers.")
    with st.sidebar:
        st.header("Mission control")
        uri = st.text_input("Atlas URI", ATLAS_URI, type="password")
        database = st.text_input("Database", "aisle_be_back")
        api_key = st.text_input("OpenAI API key", OPENAI_API_KEY, type="password")
        model = st.text_input("Vision model", DEFAULT_MODEL)
        with st.expander("Viam camera connection"):
            address = st.text_input("Machine address", VIAM_ADDRESS)
            key_id = st.text_input("Viam API key ID", VIAM_API_KEY_ID)
            key = st.text_input("Viam API key", VIAM_API_KEY, type="password")
            camera = st.text_input("Camera component name", CAMERA_NAME)
            if st.button("Find cameras", disabled=not all([address, key_id, key])):
                try:
                    names = asyncio.run(viam_action(address, key_id, key))
                    st.write(names or "No configured camera components found.")
                except Exception as exc:
                    show_error(exc, [key, uri, api_key])
        robot_id = st.text_input("Robot ID", "shelf-rover-01")
        location = {"store_id": st.text_input("Store", "demo-store"),
                    "aisle": st.text_input("Aisle", "snacks"),
                    "shelf": st.text_input("Shelf", "middle")}
        st.caption("Location and robot ID are frozen when you capture or load an image.")
        if st.button("Test Atlas", disabled=not uri):
            try:
                with mongo_client(uri) as client:
                    client.admin.command("ping")
                st.success("Atlas connected.")
            except Exception as exc:
                show_error(exc, [uri])

    scan_tab, history_tab = st.tabs(["📷 Scan & review", "🍃 Atlas history"])
    with scan_tab:
        left, right = st.columns([1, 1])
        with left:
            st.subheader("1 · Get a shelf label")
            source = st.radio("Image source", ["Viam camera", "Upload image", "Sample label"], horizontal=True)
            try:
                if source == "Viam camera":
                    if st.button("Capture from rover", type="primary", disabled=not all([address, key_id, key, camera])):
                        with st.spinner("Connecting and capturing…"):
                            raw = asyncio.run(viam_action(address, key_id, key, camera))
                            new_capture(raw, source, robot_id, location)
                elif source == "Upload image":
                    uploaded = st.file_uploader("One label per photo", type=["jpg", "jpeg", "png"])
                    if st.button("Load image", disabled=uploaded is None):
                        new_capture(uploaded.getvalue(), source, robot_id, location)
                elif st.button("Load sample label"):
                    new_capture(sample_image(), source, robot_id, location)
            except Exception as exc:
                show_error(exc, [uri, key, api_key])
            capture = st.session_state.get("capture")
            if capture:
                st.image(capture["image"], caption=f'{capture["source"]} · {capture["id"][:8]}')
                st.caption(f'Captured {capture["captured_at"].isoformat()} · {capture["location"]}')
                st.download_button("Download photo", capture["image"], "shelf-label.jpg", "image/jpeg")
        with right:
            st.subheader("2 · Extract, review, save")
            if not capture:
                st.info("Capture or load an image to begin.")
            else:
                saved = st.session_state.get("saved", False)
                st.caption("Extract sends this image to OpenAI. One request per click; no automatic retries.")
                if st.button("Extract label with AI", type="primary", disabled=not api_key or saved):
                    try:
                        with st.spinner("Reading the label…"):
                            result = extract_label(capture["image"], api_key, model)
                        st.session_state.label = result.model_dump()
                        st.session_state.extraction_model = model
                        st.session_state.revision += 1
                    except Exception as exc:
                        show_error(exc, [api_key, uri, key])
                label = st.session_state.get("label") or {}
                if label.get("concerns"):
                    st.warning(" · ".join(label["concerns"]))
                st.caption("No AI key? Enter the fields manually. This first version saves USD single-item prices.")
                form_key = capture["id"] + str(st.session_state.revision)
                with st.form(form_key):
                    name = st.text_input("Product name", label.get("product_name") or "")
                    size = st.text_input("Size", label.get("size_text") or "")
                    price = st.text_input("Single-item price (USD)", label.get("price_text") or "")
                    if label.get("currency") and label["currency"] != "USD":
                        st.warning(f"Extracted currency: {label['currency']}. Only save if the label is USD.")
                    sku = st.text_input("SKU (optional)", label.get("sku") or "")
                    barcode = st.text_input("Printed barcode digits (optional)", label.get("barcode") or "")
                    promo = st.text_input("Promotion wording (optional)", label.get("promotion_text") or "")
                    raw_text = st.text_area("Original label text", label.get("raw_label_text") or "")
                    reviewed = st.checkbox("I checked the photo, product, and single-item USD price.")
                    submit = st.form_submit_button("Save observation to Atlas", disabled=not uri or saved)
                if submit:
                    try:
                        if not reviewed or not name.strip():
                            raise ValueError("Enter a product name and confirm your review.")
                        cents = money_to_cents(price)
                        doc = {
                            "_id": capture["id"], "scan_id": capture["id"],
                            "captured_at": capture["captured_at"],
                            "saved_at": datetime.now(timezone.utc),
                            "robot_id": capture["robot_id"], "location": capture["location"],
                            "product": {"label_name": name.strip(), "size_text": size.strip() or None,
                                        "sku": sku.strip() or None, "barcode": barcode.strip() or None},
                            "price": {"amount_minor": cents, "currency": "USD", "promotion_text": promo or None},
                            "capture": {"source": capture["source"], "image_jpeg": capture["image"],
                                        "sha256": hashlib.sha256(capture["image"]).hexdigest(),
                                        "raw_label_text": raw_text},
                            "extraction": {"method": "openai_vision" if label else "manual",
                                           "model": st.session_state.extraction_model,
                                           "original_output": label or None, "review_status": "human_reviewed"},
                        }
                        inserted = save_observation(uri, database, doc)
                        st.session_state.saved = True
                        st.success("Saved to Atlas." if inserted else "This capture is already in Atlas; no duplicate created.")
                    except Exception as exc:
                        show_error(exc, [uri, api_key, key])
                if saved:
                    st.success("This capture is saved. Load or capture another image for a new observation.")
    with history_tab:
        st.subheader("Shelf memories")
        st.caption("Loads up to 100 recent observations. Filter by exact SKU and store; sample captures are excluded by default.")
        filter_sku = st.text_input("Filter SKU (optional)")
        filter_store = st.text_input("Filter store (optional)")
        samples = st.checkbox("Include sample-label captures")
        if st.button("Refresh history", disabled=not uri):
            try:
                query = {}
                if filter_sku.strip():
                    query["product.sku"] = filter_sku.strip()
                if filter_store.strip():
                    query["location.store_id"] = filter_store.strip()
                if not samples:
                    query["capture.source"] = {"$ne": "Sample label"}
                with mongo_client(uri) as client:
                    docs = list(client[database].price_observations.find(
                        query, {"capture.image_jpeg": 0}).sort("captured_at", -1).limit(100))
                rows = [{"Time": d["captured_at"], "Product": d["product"]["label_name"],
                         "SKU": d["product"].get("sku"), "USD": d["price"]["amount_minor"] / 100,
                         "Store": d["location"]["store_id"], "Source": d["capture"]["source"]} for d in docs]
                st.dataframe(rows, use_container_width=True)
                if filter_sku.strip() and filter_store.strip() and rows:
                    st.line_chart([{ "Time": r["Time"], "USD": r["USD"]} for r in reversed(rows)], x="Time", y="USD")
                elif rows:
                    st.info("Enter both SKU and store to chart a single product's observed prices.")
            except Exception as exc:
                show_error(exc, [uri])
    st.caption("Aisle be back. With receipts. 🤖🧾")


if __name__ == "__main__":
    main()
