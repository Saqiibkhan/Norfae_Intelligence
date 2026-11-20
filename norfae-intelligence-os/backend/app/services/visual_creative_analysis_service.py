from io import BytesIO

from app.schemas.creative_schema import VisualAssetAnalysis

MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_IMAGE_PIXELS = 40_000_000
SUPPORTED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}


class VisualCreativeAnalysisService:
    """Optional, local image metadata/color analysis; never contacts external APIs."""

    @staticmethod
    def analyze_image(asset: bytes | None, media_type: str | None) -> VisualAssetAnalysis:
        if not asset:
            return VisualAssetAnalysis(
                status="unavailable", media_kind="image", width=None, height=None,
                aspect_ratio=None, dominant_colors=[], warnings=["No image asset is stored or available for this creative."],
            )
        if media_type not in SUPPORTED_IMAGE_TYPES:
            return VisualAssetAnalysis(
                status="unsupported", media_kind="image", width=None, height=None,
                aspect_ratio=None, dominant_colors=[], warnings=["Only JPEG, PNG, WebP, and GIF images are supported."],
            )
        if len(asset) > MAX_IMAGE_BYTES:
            return VisualAssetAnalysis(
                status="unsupported", media_kind="image", width=None, height=None,
                aspect_ratio=None, dominant_colors=[], warnings=["Image exceeds the 10 MiB analysis limit."],
            )
        try:
            from PIL import Image

            with Image.open(BytesIO(asset)) as image:
                if image.format not in {"JPEG", "PNG", "WEBP", "GIF"}:
                    raise ValueError("Unsupported image encoding.")
                width, height = image.size
                if width <= 0 or height <= 0 or width * height > MAX_IMAGE_PIXELS:
                    raise ValueError("Image dimensions exceed the analysis limit.")
                image.load()
                rgb = image.convert("RGB")
                quantized = rgb.resize((min(width, 256), min(height, 256))).quantize(colors=5)
                palette = quantized.getpalette() or []
                histogram = quantized.getcolors(maxcolors=256) or []
                colors = []
                for _count, color_index in sorted(histogram, key=lambda pair: pair[0], reverse=True)[:5]:
                    offset = color_index * 3
                    colors.append("#%02X%02X%02X" % tuple(palette[offset : offset + 3]))
            return VisualAssetAnalysis(
                status="analyzed", media_kind="image", width=width, height=height,
                aspect_ratio=round(width / height, 4), dominant_colors=colors,
                warnings=[
                    "Color and geometry only; OCR, product recognition, and composition interpretation are not performed.",
                    "Visual attributes are not linked to advertising outcomes and do not imply causation.",
                ],
            )
        except ImportError:
            return VisualAssetAnalysis(
                status="unavailable", media_kind="image", width=None, height=None,
                aspect_ratio=None, dominant_colors=[], warnings=["Optional Pillow library is not installed."],
            )
        except Exception:
            return VisualAssetAnalysis(
                status="failed", media_kind="image", width=None, height=None,
                aspect_ratio=None, dominant_colors=[], warnings=["Image could not be safely decoded for local analysis."],
            )

    @staticmethod
    def analyze_video(_asset: bytes | None) -> VisualAssetAnalysis:
        return VisualAssetAnalysis(
            status="unavailable" if not _asset else "unsupported",
            media_kind="video", width=None, height=None, aspect_ratio=None,
            dominant_colors=[], warnings=[
                "No video asset is stored for existing creatives." if not _asset
                else "Video decoding is not supported; no video-analysis dependency is installed."
            ],
        )
