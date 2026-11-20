"""Small non-cryptographic hash fallback for restricted Python environments.

LangGraph uses xxhash for ephemeral task identifiers. Some locked-down Windows
hosts block the xxhash native extension; BLAKE2b supplies the same-sized,
non-cryptographic identifier surface for request-scoped graphs without state
checkpointing. The normal xxhash implementation is preferred when importable.
"""

import hashlib
import sys
from types import ModuleType


class _Digest128:
    def __init__(self, value: bytes):
        self._digest = hashlib.blake2b(value, digest_size=16).digest()

    def digest(self) -> bytes:
        return self._digest

    def hexdigest(self) -> str:
        return self._digest.hex()

    def intdigest(self) -> int:
        return int.from_bytes(self._digest, "little")


def install_xxhash_fallback() -> bool:
    """Install only when native xxhash cannot be loaded; return fallback status."""
    try:
        import xxhash  # noqa: F401
        return False
    except (ImportError, OSError):
        compatibility_module = ModuleType("xxhash")
        compatibility_module.xxh3_128 = _Digest128
        compatibility_module.xxh3_128_hexdigest = lambda value: _Digest128(value).hexdigest()
        compatibility_module.xxh3_128_digest = lambda value: _Digest128(value).digest()
        compatibility_module.xxh3_128_intdigest = lambda value: _Digest128(value).intdigest()
        compatibility_module.__norfae_fallback__ = True
        sys.modules["xxhash"] = compatibility_module
        return True
