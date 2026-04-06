from __future__ import annotations

import io
import re
from functools import lru_cache
from typing import Sequence


def _load_ocr_dependencies():
    try:
        import easyocr  # type: ignore[import-not-found]
        import numpy as np  # type: ignore[import-not-found]
        from PIL import Image  # type: ignore[import-not-found]
    except ImportError as exc:  # pragma: no cover - depends on optional runtime deps
        raise RuntimeError(
            "OCR support requires optional dependencies. Install with: pip install easyocr numpy pillow"
        ) from exc
    return easyocr, np, Image


class OCRHelper:
    def __init__(self, languages: Sequence[str] | None = None, *, use_gpu: bool = False) -> None:
        self.languages = tuple(languages or ("ch_sim", "en"))
        self.use_gpu = use_gpu
        self._reader = None

    def _ensure_reader(self):
        easyocr, _, _ = _load_ocr_dependencies()
        if self._reader is None:
            self._reader = easyocr.Reader(list(self.languages), gpu=self.use_gpu)
        return self._reader

    def _crop_region(self, image_bytes: bytes, region: tuple[int, int, int, int]):
        _, np, Image = _load_ocr_dependencies()
        x1, y1, x2, y2 = region
        if x2 <= x1 or y2 <= y1:
            raise ValueError(f"Invalid OCR region: {region!r}")

        with Image.open(io.BytesIO(image_bytes)) as image:
            image = image.convert("RGB")
            left = max(int(x1), 0)
            top = max(int(y1), 0)
            right = min(int(x2), image.width)
            bottom = min(int(y2), image.height)
            if right <= left or bottom <= top:
                raise ValueError(f"OCR region {region!r} is outside screenshot bounds")
            cropped = image.crop((left, top, right, bottom))
            return np.array(cropped)

    def recognize_region_text(self, image_bytes: bytes, region: tuple[int, int, int, int]) -> str:
        reader = self._ensure_reader()
        image_array = self._crop_region(image_bytes, region)
        results = reader.readtext(image_array, detail=0, paragraph=True)
        if not results:
            return ""
        return " ".join(str(item).strip() for item in results if str(item).strip()).strip()

    def recognize_region_number(self, image_bytes: bytes, region: tuple[int, int, int, int]) -> int | float:
        text = self.recognize_region_text(image_bytes, region)
        normalized = text.replace(",", "").replace(" ", "")
        normalized = re.sub(r"[^0-9.\-]+", "", normalized)
        if normalized in {"", "-", ".", "-."}:
            raise ValueError(f"OCR region does not contain a numeric value: {text!r}")
        value = float(normalized)
        if value.is_integer():
            return int(value)
        return value


@lru_cache(maxsize=4)
def get_ocr_helper(languages: tuple[str, ...] = ("ch_sim", "en"), use_gpu: bool = False) -> OCRHelper:
    return OCRHelper(languages=languages, use_gpu=use_gpu)
