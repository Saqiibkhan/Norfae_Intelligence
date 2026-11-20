import re

import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.city_detection_service import CityDetectionService

from app.services.city_normalization_service import CityNormalizationService

# ======================================
# EXTRACT FIELD
# ======================================


def extract_value(patterns, text):

    for pattern in patterns:

        match = re.search(pattern, text, re.IGNORECASE)

        if match:

            return match.group(1).strip()

    return None


# ======================================
# DETECT SOURCE
# ======================================


def detect_source(order_id):

    if not order_id:

        return "UNKNOWN"

    normalized = order_id.replace("#", "").replace("NRF-", "").strip().upper()

    # ==============================
    # INSTAGRAM
    # ==============================

    if normalized.startswith("IG"):

        return "INSTAGRAM"

    # ==============================
    # SHOPIFY
    # ==============================

    if normalized.isdigit():

        return "SHOPIFY"

    return "UNKNOWN"


# ======================================
# CLEAN ORDER ID
# ======================================


def clean_order_id(order_id):

    if not order_id:

        return None

    cleaned = order_id.replace("NRF-", "").replace("#", "").strip()

    return cleaned


# ======================================
# EXTRACT CITY
# ======================================


def extract_city(address):

    if not address:

        return "Unknown"

    cities = [
        "lahore",
        "karachi",
        "islamabad",
        "rawalpindi",
        "faisalabad",
        "multan",
        "peshawar",
        "quetta",
        "sialkot",
        "gujranwala",
        "sheikhupura",
        "gujrat",
        "sahiwal",
        "abbottabad",
        "lodhran",
    ]

    address_lower = address.lower()

    for city in cities:

        if city in address_lower:

            return city.title()

    return "Unknown"


# ======================================
# EXTRACT TOTAL
# ======================================


def extract_total(text):

    total_patterns = [r"Total\s*:\s*(.+)", r"Total Price\s*:\s*(.+)"]

    for pattern in total_patterns:

        match = re.search(pattern, text, re.IGNORECASE)

        if match:

            raw = match.group(1)

            digits = re.findall(r"\d+", raw.replace(",", ""))

            if digits:

                return float(digits[0])

    price_patterns = [r"Price\s*:\s*(.+)"]

    for pattern in price_patterns:

        match = re.search(pattern, text, re.IGNORECASE)

        if match:

            raw = match.group(1)

            digits = re.findall(r"\d+", raw.replace(",", ""))

            if digits:

                return float(digits[0])

    return 0


# ======================================
# NORMALIZE SIZE
# ======================================


def normalize_size(size):

    if not size:

        return None

    return size.replace(" ", "").lower().strip()


# ======================================
# EXTRACT SIZE
# ======================================


def extract_size(text):

    match = re.search(r"(\d+(?:\.\d+)?\s*(?:cm|feet|ft))", text, re.IGNORECASE)

    if not match:

        return None

    return normalize_size(match.group(1))


# ======================================
# CLEAN PRODUCT NAME
# ======================================


def clean_product_name(name):

    if not name:

        return None

    # ==================================
    # LOWER
    # ==================================

    name = str(name).strip()

    # ==================================
    # REMOVE SIZE
    # ==================================

    name = re.sub(r"\d+(?:\.\d+)?\s*(?:cm|feet|ft)", "", name, flags=re.IGNORECASE)

    # ==================================
    # REMOVE QUANTITY
    # ==================================

    name = re.sub(r"x\d+", "", name, flags=re.IGNORECASE)

    # ==================================
    # REMOVE SPECIALS
    # ==================================

    name = re.sub(r"[:,]", " ", name)

    # ==================================
    # REMOVE EXTRA SPACES
    # ==================================

    name = re.sub(r"\s+", " ", name).strip()

    # ==================================
    # INVALID SHORT NAMES
    # ==================================

    invalid_exact = [
        "size",
        "product",
        "products",
        "stuffed toy",
        "toy",
        "plush",
        "plushie",
        "teddy",
        "price",
        "total",
        "discount",
        "payment",
        "qty",
        "quantity",
    ]

    if name.lower() in invalid_exact:

        return None

    # ==================================
    # INVALID CONTAINS
    # ==================================

    invalid_contains = [
        "address",
        "phone",
        "contact",
        "delivery",
        "cod",
        "bank",
        "easypaisa",
        "jazzcash",
    ]

    lowered = name.lower()

    if any(x in lowered for x in invalid_contains):

        return None

    # ==================================
    # TOO SHORT
    # ==================================

    if len(name.strip()) <= 2:

        return None

    # ==================================
    # WORD COUNT SAFETY
    # ==================================

    words = name.split()

    if len(words) > 8:

        return None

    return name


# ======================================
# PARSE SINGLE PRODUCT
# ======================================


def parse_single_product_logic(order_text, products):

    single_product = extract_value(
        [
            r"Stuffed Toy\s*:\s*(.+)",
            r"Products\s*:\s*(.+)",
            r"Product\s*:\s*(.+)",
            r"Plushie\s*:\s*(.+)",
            r"Plush\s*:\s*(.+)",
            r"Teddy\s*:\s*(.+)",
            r"Stuff toy\s*:\s*(.+)",
        ],
        order_text,
    )

    if not single_product:

        return products

    # ==============================
    # SIZE
    # ==============================

    size = extract_size(single_product)

    # ==============================
    # QUANTITY
    # ==============================

    quantity_match = re.search(r"x(\d+)", single_product, re.IGNORECASE)

    quantity = 1

    if quantity_match:

        quantity = int(quantity_match.group(1))

    # ==============================
    # CLEAN NAME
    # ==============================

    clean_name = clean_product_name(single_product)

    if not clean_name:

        return products

    clean_name = re.sub(r"\d+\s*cm", "", clean_name, flags=re.IGNORECASE)

    clean_name = re.sub(r"[:,]", " ", clean_name)

    clean_name = re.sub(r"\s+", " ", clean_name).strip()

    # ==============================
    # FINAL VALIDATION
    # ==============================

    invalid_words = ["which", "with", "without", "for", "and", "or"]

    clean_words = clean_name.lower().split()

    if len(clean_words) == 1:

        if clean_words[0] in invalid_words:

            return products

    products.append({"name": clean_name, "quantity": quantity, "size": size})

    return products


# ======================================
# PARSE MULTI PRODUCT
# ======================================


def parse_multi_product_logic(order_text, products):

    # ==================================
    # NUMBERED PRODUCTS
    # ==================================

    numbered_product_blocks = re.finditer(
        r"Product\s*(\d+)\s*:\s*(.*?)" r"(.*?)(?=Product\s*\d+\s*:|Discount|Total|$)",
        order_text,
        re.IGNORECASE | re.DOTALL,
    )

    found_numbered_products = False

    for block in numbered_product_blocks:

        found_numbered_products = True

        raw_name = block.group(2).strip()

        block_content = block.group(3).strip()

        raw_size = None

        size_match = re.search(
            r"Size\s*:\s*(\d+(?:\.\d+)?\s*(?:cm|feet|ft))", block_content, re.IGNORECASE
        )

        if size_match:

            raw_size = normalize_size(size_match.group(1))

        # ==============================
        # CLEAN NAME
        # ==============================

        clean_name = clean_product_name(raw_name)

        if not clean_name:

            continue

        # ==============================
        # FINAL VALIDATION
        # ==============================

        invalid_words = ["which", "with", "without", "for", "and", "or"]

        clean_words = clean_name.lower().split()

        if len(clean_words) == 1:

            if clean_words[0] in invalid_words:

                continue

        # ==============================
        # SAVE PRODUCT
        # ==============================

        products.append({"name": clean_name, "quantity": 1, "size": raw_size})

    if found_numbered_products:

        return products

    # ==================================
    # MULTILINE PRODUCT BLOCK
    # ==================================

    product_block_match = re.search(
        r"Product\s*:\s*(.*?)(?:\n\s*Total|\Z)", order_text, re.IGNORECASE | re.DOTALL
    )

    products_raw = None

    if product_block_match:

        products_raw = product_block_match.group(1).strip()

    else:

        products_raw = extract_value(
            [
                r"Stuffed Toy\s*:\s*(.+)",
                r"Products\s*:\s*(.+)",
                r"Plushie\s*:\s*(.+)",
                r"Plush\s*:\s*(.+)",
                r"Teddy\s*:\s*(.+)",
                r"Stuff toy\s*:\s*(.+)",
            ],
            order_text,
        )

    if not products_raw:

        return products

    # ==================================
    # SPLIT PRODUCTS
    # ==================================

    if "\n" in products_raw:

        split_products = []

        for line in products_raw.split("\n"):

            line = line.strip()

            if not line:

                continue

            invalid_lines = [
                "product",
                "total",
                "discount",
                "payment",
                "price",
                "size",
                "quantity",
                "address",
                "phone",
                "contact",
                "cod",
                "delivery",
            ]

            lowered_line = line.lower().strip()

            if lowered_line in invalid_lines:

                continue

            split_products.append(line)

    else:

        split_products = re.split(r",|\+|&", products_raw)
    # ==================================
    # LOOP PRODUCTS
    # ==================================

    for item in split_products:

        product_line = item.strip()

        if not product_line:

            continue

        # ==============================
        # QUANTITY
        # ==============================

        quantity_match = re.search(r"x(\d+)", product_line, re.IGNORECASE)

        quantity = 1

        if quantity_match:

            quantity = int(quantity_match.group(1))

        # ==============================
        # SIZE
        # ==============================

        size_match = re.search(
            r"(\d+(?:\.\d+)?\s*(?:cm|feet|ft))", product_line, re.IGNORECASE
        )

        size = None

        if size_match:

            size = size_match.group(1).replace(" ", "").lower()

        # ==============================
        # CLEAN NAME
        # ==============================

        clean_name = clean_product_name(product_line)

        if not clean_name:

            continue

        # ==============================
        # FINAL VALIDATION
        # ==============================

        invalid_words = ["which", "with", "without", "for", "and", "or"]

        clean_words = clean_name.lower().split()

        if len(clean_words) == 1:

            if clean_words[0] in invalid_words:

                continue

        # ==============================
        # SAVE PRODUCT
        # ==============================

        products.append({"name": clean_name, "quantity": quantity, "size": size})
    return products


# ======================================
# PARSE SINGLE ORDER
# ======================================


def parse_single_order(order_text):

    # ==================================
    # ORDER ID
    # ==================================

    order_id = extract_value(
        [r"Order\s*(?:ID|Id|id|number|no)\s*:?\s*(.+)"], order_text
    )

    if order_id:

        order_id = order_id.split(",")[0].strip()

    order_id = clean_order_id(order_id)

    # ==================================
    # CUSTOMER NAME
    # ==================================

    customer_name = extract_value(
        [r"Full Name\s*:\s*(.+)", r"Name\s*:\s*(.+)"], order_text
    )

    # ==================================
    # PHONE
    # ==================================

    phone = extract_value(
        [
            r"Contact Number\s*📞?\s*:\s*(.+)",
            r"Contact Number\s*:\s*(.+)",
            r"Contact\s*:\s*(.+)",
            r"Phone no\s*:\s*(.+)",
            r"Phone\s*:\s*(.+)",
            r"Mob\s*:\s*(.+)",
            r"Mobile\s*:\s*(.+)",
            r"No\.\s*(.+)",
        ],
        order_text,
    )

    # ==================================
    # ADDRESS
    # ==================================

    address = extract_value(
        [
            r"Delivery Address\s*:\s*(.+)",
            r"Complete Address\s*:\s*(.+)",
            r"Address\s*:\s*(.+)",
            r"Adress\s*:\s*(.+)",
            r"Addresz\s*:\s*(.+)",
        ],
        order_text,
    )

    # ==================================
    # PRODUCTS
    # ==================================

    products = []

    raw_product_section = extract_value(
        [
            r"Stuffed Toy\s*:\s*(.+)",
            r"Products\s*:\s*(.+)",
            r"Product\s*:\s*(.+)",
            r"Plushie\s*:\s*(.+)",
            r"Plush\s*:\s*(.+)",
            r"Teddy\s*:\s*(.+)",
            r"Stuff toy\s*:\s*(.+)",
        ],
        order_text,
    )

    if not raw_product_section:

        raw_product_section = ""

    # ==================================
    # MULTI PRODUCT DETECTION
    # ==================================

    is_numbered_products = bool(
        re.search(r"Product\s*\d+\s*:", order_text, re.IGNORECASE)
    )

    is_multiline_products = "\n" in raw_product_section

    is_ampersand_products = "&" in raw_product_section

    is_multi_product = (
        is_numbered_products or is_multiline_products or is_ampersand_products
    )

    # ==================================
    # SINGLE PRODUCT FLOW
    # ==================================

    if not is_multi_product:

        products = parse_single_product_logic(order_text, products)

    # ==================================
    # MULTI PRODUCT FLOW
    # ==================================

    else:

        products = parse_multi_product_logic(order_text, products)

    # ==================================
    # FALLBACK DISPLAY PRODUCT
    # ==================================

    product = None

    if products:

        product = products[0]["name"]

    # ==================================
    # SIZE
    # ==================================

    size = extract_value([r"Size\s*:\s*(.+)"], order_text)

    # ==================================
    # TOTAL
    # ==================================

    total = extract_total(order_text)

    # ==================================
    # CITY
    # ==================================

    detected_city = CityDetectionService.detect_city(address or "")

    city = CityNormalizationService.normalize_city(detected_city)

    # ==================================
    # SOURCE
    # ==================================

    source = detect_source(order_id)

    # ==================================
    # INVALID
    # ==================================

    if not order_id:

        return None

    return {
        "order_id": order_id,
        "customer_name": customer_name,
        "phone": phone,
        "address": address,
        "city": city,
        "product": product,
        "products": products,
        "size": size,
        "total": total,
        "source": source,
    }


# ======================================
# PARSE MULTIPLE ORDERS
# ======================================


def parse_order_message(message_content):

    order_blocks = re.split(
        r"(?=Order\s*(?:ID|Id|id|number|no))", message_content, flags=re.IGNORECASE
    )

    parsed_orders = []

    for block in order_blocks:

        block = block.strip()

        if not block:

            continue

        parsed = parse_single_order(block)

        if parsed:

            parsed_orders.append(parsed)

    return parsed_orders
