from sqlalchemy.orm import Session

from difflib import SequenceMatcher

from app.models.inventory_product_model import InventoryProduct

from app.models.product_match_memory_model import ProductMatchMemory

from app.services.product_normalization_service import ProductNormalizationService


class InventoryMatchService:

    # ===================================
    # TEXT SIMILARITY
    # ===================================

    @staticmethod
    def similarity(a, b):

        return SequenceMatcher(None, a, b).ratio()

    # ===================================
    # NORMALIZE SIZE
    # ===================================

    @staticmethod
    def normalize_size(size):

        if not size:

            return None

        return str(size).replace(" ", "").lower().strip()

    # ===================================
    # TOKENIZE
    # ===================================

    @staticmethod
    def tokenize(text):

        if not text:

            return set()

        return set(text.lower().split())

    # ===================================
    # MEMORY MATCH
    # ===================================

    @staticmethod
    def get_memory_match(
        db: Session, normalized_name: str, normalized_size: str = None
    ):

        memory_match = (
            db.query(ProductMatchMemory)
            .filter(
                ProductMatchMemory.normalized_name == normalized_name,
                ProductMatchMemory.normalized_size == normalized_size,
            )
            .order_by(ProductMatchMemory.confidence_score.desc())
            .first()
        )

        if not memory_match:

            return None

        inventory_product = (
            db.query(InventoryProduct)
            .filter(InventoryProduct.sku == memory_match.matched_sku)
            .first()
        )

        if inventory_product:

            print(
                "[MEMORY MATCH]",
                normalized_name,
                normalized_size,
                "->",
                inventory_product.sku,
            )

            return inventory_product

        return None

    # ===================================
    # SAVE MEMORY
    # ===================================

    @staticmethod
    def save_match_memory(
        db: Session,
        raw_product_name: str,
        normalized_name: str,
        raw_size: str,
        normalized_size: str,
        raw_price: float,
        matched_product,
        confidence_score: float,
    ):

        existing_memory = (
            db.query(ProductMatchMemory)
            .filter(
                ProductMatchMemory.normalized_name == normalized_name,
                ProductMatchMemory.normalized_size == normalized_size,
                ProductMatchMemory.matched_sku == matched_product.sku,
            )
            .first()
        )

        if existing_memory:

            return

        memory = ProductMatchMemory(
            raw_product_name=raw_product_name,
            normalized_name=normalized_name,
            normalized_size=normalized_size,
            raw_size=raw_size,
            raw_price=raw_price,
            matched_sku=matched_product.sku,
            matched_product_name=matched_product.product_name,
            confidence_score=confidence_score,
        )

        db.add(memory)

        db.commit()

        print(
            "[MEMORY SAVED]",
            normalized_name,
            normalized_size,
            "->",
            matched_product.sku,
        )

    # ===================================
    # SINGLE PRODUCT MATCHING
    # ===================================

    @staticmethod
    def match_single_product(
        db: Session, product_name: str, selling_price: float, size: str = None
    ):

        normalized_order = ProductNormalizationService.normalize_product_name(
            product_name
        )

        normalized_size = InventoryMatchService.normalize_size(size)

        # ===================================
        # MEMORY FIRST
        # ===================================

        memory_match = InventoryMatchService.get_memory_match(
            db=db, normalized_name=normalized_order, normalized_size=normalized_size
        )

        if memory_match:

            return memory_match

        # ===================================
        # TOKENIZATION
        # ===================================

        order_tokens = InventoryMatchService.tokenize(normalized_order)

        inventory_products = db.query(InventoryProduct).all()

        best_match = None

        best_score = 0

        # ===================================
        # LOOP INVENTORY
        # ===================================

        for product in inventory_products:

            inventory_name = ProductNormalizationService.normalize_product_name(
                product.product_name or ""
            )

            inventory_tokens = InventoryMatchService.tokenize(inventory_name)

            # ===================================
            # COMMON TOKENS
            # ===================================

            common_tokens = order_tokens & inventory_tokens

            if len(common_tokens) == 0:

                continue

            # ===================================
            # IMPORTANT TOKENS
            # ===================================

            important_tokens = [token for token in order_tokens if len(token) > 3]

            matched_important = [
                token for token in important_tokens if token in inventory_tokens
            ]

            # ===================================
            # IMPORTANT COVERAGE
            # ===================================

            important_coverage = 0

            if important_tokens:

                important_coverage = len(matched_important) / len(important_tokens)

            # ===================================
            # STRICT VALIDATION
            # ===================================

            if important_tokens and important_coverage < 0.6:

                continue

            if important_tokens and len(matched_important) == 0:

                continue

            # ===================================
            # SIZE VALIDATION
            # ===================================

            inventory_size = InventoryMatchService.normalize_size(product.size)

            if normalized_size:

                if inventory_size != normalized_size:

                    continue

            # ===================================
            # BASE SIMILARITY
            # ===================================

            score = InventoryMatchService.similarity(normalized_order, inventory_name)

            # ===================================
            # EXTRA TOKEN PENALTY
            # ===================================

            extra_tokens = inventory_tokens - order_tokens

            score -= len(extra_tokens) * 0.15

            # ===================================
            # TOKEN BOOST
            # ===================================

            score += len(common_tokens) * 0.25

            # ===================================
            # SIZE BOOST
            # ===================================

            if normalized_size and inventory_size == normalized_size:

                score += 2.0

            # ===================================
            # PRICE VALIDATION
            # ===================================

            inventory_price = float(product.selling_price or 0)

            price_difference = abs(inventory_price - float(selling_price))

            # ===================================
            # HARD PRICE REJECTION
            # ===================================

            if price_difference > 2500:

                continue

            if price_difference <= 300:

                score += 0.5

            if price_difference <= 100:

                score += 1.0

            if price_difference <= 50:

                score += 2.0

            # ===================================
            # EXACT NAME BONUS
            # ===================================

            if normalized_order == inventory_name:

                score += 3

            # ===================================
            # BEST MATCH
            # ===================================

            if score > best_score:

                best_score = score

                best_match = product

        # ===================================
        # SAVE MEMORY
        # ===================================

        if best_match and best_score >= 4:

            InventoryMatchService.save_match_memory(
                db=db,
                raw_product_name=product_name,
                normalized_name=normalized_order,
                raw_size=size,
                normalized_size=normalized_size,
                raw_price=selling_price,
                matched_product=best_match,
                confidence_score=best_score,
            )

            return best_match

        return None

    # ===================================
    # MULTI PRODUCT MATCHING
    # ===================================

    @staticmethod
    def match_multi_product(db: Session, product_name: str, size: str = None):

        normalized_order = ProductNormalizationService.normalize_product_name(
            product_name
        )

        normalized_size = InventoryMatchService.normalize_size(size)

        # ===================================
        # MEMORY FIRST
        # ===================================

        memory_match = InventoryMatchService.get_memory_match(
            db=db, normalized_name=normalized_order, normalized_size=normalized_size
        )

        if memory_match:

            return memory_match

        # ===================================
        # TOKENIZATION
        # ===================================

        order_tokens = InventoryMatchService.tokenize(normalized_order)

        inventory_products = db.query(InventoryProduct).all()

        best_match = None

        best_score = 0

        # ===================================
        # LOOP INVENTORY
        # ===================================

        for product in inventory_products:

            inventory_name = ProductNormalizationService.normalize_product_name(
                product.product_name or ""
            )

            inventory_tokens = InventoryMatchService.tokenize(inventory_name)

            # ===================================
            # TOKEN VALIDATION
            # ===================================

            common_tokens = order_tokens & inventory_tokens

            if len(common_tokens) == 0:

                continue

            important_tokens = [token for token in order_tokens if len(token) > 3]

            matched_important = [
                token for token in important_tokens if token in inventory_tokens
            ]

            # ===================================
            # IMPORTANT COVERAGE
            # ===================================

            important_coverage = 0

            if important_tokens:

                important_coverage = len(matched_important) / len(important_tokens)

            # ===================================
            # STRICT VALIDATION
            # ===================================

            if important_tokens and important_coverage < 0.6:

                continue

            if important_tokens and len(matched_important) == 0:

                continue

            # ===================================
            # SIZE VALIDATION
            # ===================================

            inventory_size = InventoryMatchService.normalize_size(product.size)

            if normalized_size:

                if inventory_size != normalized_size:

                    continue

            # ===================================
            # BASE SIMILARITY
            # ===================================

            score = InventoryMatchService.similarity(normalized_order, inventory_name)

            # ===================================
            # EXTRA TOKEN PENALTY
            # ===================================

            extra_tokens = inventory_tokens - order_tokens

            score -= len(extra_tokens) * 0.15

            # ===================================
            # TOKEN BOOST
            # ===================================

            score += len(common_tokens) * 0.25

            # ===================================
            # SIZE BOOST
            # ===================================

            if normalized_size and inventory_size == normalized_size:

                score += 2.0

            # ===================================
            # EXACT NAME BONUS
            # ===================================

            if normalized_order == inventory_name:

                score += 3

            # ===================================
            # BEST MATCH
            # ===================================

            if score > best_score:

                best_score = score

                best_match = product

        # ===================================
        # SAVE MEMORY
        # ===================================

        if best_match and best_score >= 4:

            InventoryMatchService.save_match_memory(
                db=db,
                raw_product_name=product_name,
                normalized_name=normalized_order,
                raw_size=size,
                normalized_size=normalized_size,
                raw_price=0,
                matched_product=best_match,
                confidence_score=best_score,
            )

            return best_match

        return None

    # ===================================
    # MAIN MATCHER
    # ===================================

    @staticmethod
    def find_matching_inventory_product(
        db: Session,
        product_name: str,
        selling_price: float,
        size: str = None,
        is_multi_product: bool = False,
    ):

        if not product_name:

            return None

        # ===================================
        # SINGLE PRODUCT FLOW
        # ===================================

        if not is_multi_product:

            return InventoryMatchService.match_single_product(
                db=db, product_name=product_name, selling_price=selling_price, size=size
            )

        # ===================================
        # MULTI PRODUCT FLOW
        # ===================================

        return InventoryMatchService.match_multi_product(
            db=db, product_name=product_name, size=size
        )
