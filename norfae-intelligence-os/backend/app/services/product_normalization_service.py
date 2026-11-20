import re

from difflib import SequenceMatcher


class ProductNormalizationService:

    # ===================================
    # REMOVE DUPLICATE WORDS
    # ===================================

    @staticmethod
    def remove_duplicate_words(words):

        seen = []

        for word in words:

            if word not in seen:

                seen.append(word)

        return seen

    # ===================================
    # STEM WORD
    # ===================================

    @staticmethod
    def stem_word(word):

        if not word:

            return ""

        word = word.lower().strip()

        # ===================================
        # REMOVE COMMON ENDINGS
        # ===================================

        endings = ["ing", "ed", "ies", "es", "s"]

        for ending in endings:

            if word.endswith(ending) and len(word) > len(ending) + 2:

                word = word[: -len(ending)]

                break

        return word

    # ===================================
    # CLEAN TEXT
    # ===================================

    @staticmethod
    def clean_text(text: str):

        if not text:

            return ""

        text = str(text).lower()

        # ===================================
        # REMOVE SPECIAL CHARACTERS
        # ===================================

        text = re.sub(r"[^a-z0-9\s]", " ", text)

        # ===================================
        # NORMALIZE SIZE FORMATS
        # ===================================

        text = text.replace(" centimeter", "cm")

        text = text.replace(" centimeters", "cm")

        text = text.replace(" cm", "cm")

        text = text.replace(" feet", "ft")

        text = text.replace(" foot", "ft")

        text = text.replace(" ft", "ft")

        # ===================================
        # REMOVE EXTRA SPACES
        # ===================================

        text = re.sub(r"\s+", " ", text).strip()

        return text

    # ===================================
    # TOKENIZE
    # ===================================

    @staticmethod
    def tokenize(text):

        if not text:

            return []

        return text.split()

    # ===================================
    # NORMALIZE PRODUCT NAME
    # ===================================

    @staticmethod
    def normalize_product_name(product_name: str):

        # ===================================
        # CLEAN
        # ===================================

        text = ProductNormalizationService.clean_text(product_name)

        # ===================================
        # TOKENIZE
        # ===================================

        words = ProductNormalizationService.tokenize(text)

        # ===================================
        # STEMMING
        # ===================================

        normalized_words = []

        for word in words:

            stemmed = ProductNormalizationService.stem_word(word)

            if stemmed:

                normalized_words.append(stemmed)

        # ===================================
        # REMOVE DUPLICATES
        # ===================================

        normalized_words = ProductNormalizationService.remove_duplicate_words(
            normalized_words
        )

        # ===================================
        # SORT WORDS
        # ===================================

        normalized_words.sort()

        # ===================================
        # FINAL NORMALIZED NAME
        # ===================================

        return " ".join(normalized_words)

    # ===================================
    # TEXT SIMILARITY
    # ===================================

    @staticmethod
    def similarity(a, b):

        return SequenceMatcher(None, a, b).ratio()
