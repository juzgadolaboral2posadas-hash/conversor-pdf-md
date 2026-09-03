"""Motor de conversión PDF -> Markdown.

Estrategia por página:
- Si la página tiene texto nativo (PDF digital), se extrae con pymupdf4llm
  preservando estructura (títulos, tablas, listas).
- Si la página no tiene texto (escaneo/imagen), se renderiza a imagen y se
  aplica OCR con Tesseract, insertando el texto plano resultante.

Cada PDF de la carpeta de entrada produce un archivo .md homónimo en la
carpeta de salida.
"""
from __future__ import annotations

import io
import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

import pymupdf as fitz  # PyMuPDF
import pymupdf4llm
import pytesseract
from PIL import Image

MIN_NATIVE_CHARS = 20  # por debajo de esto, se considera "sin texto" -> OCR
OCR_DPI = 300

# Rutas típicas donde queda instalado Tesseract si no está en el PATH.
_WINDOWS_TESSERACT_CANDIDATES = [
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
]
_MAC_TESSERACT_CANDIDATES = [
    "/opt/homebrew/bin/tesseract",  # Apple Silicon (Homebrew)
    "/usr/local/bin/tesseract",  # Intel (Homebrew)
]

# Ruta relativa al ejecutable/script donde puede venir un Tesseract
# empaquetado junto a la app (ver .github/workflows/build.yml), para que el
# usuario final no tenga que instalar nada aparte.
_BUNDLED_DIRNAME = "tesseract-bin"

_bundled_tessdata_dir: Optional[Path] = None


def _app_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def _bundled_tesseract_path() -> Optional[Path]:
    exe_name = "tesseract.exe" if sys.platform == "win32" else "tesseract"
    candidate = _app_base_dir() / _BUNDLED_DIRNAME / exe_name
    return candidate if candidate.is_file() else None


def locate_tesseract() -> Optional[str]:
    """Busca Tesseract: primero uno empaquetado junto a la app, después en
    el PATH del sistema y en ubicaciones típicas de instalación."""
    bundled = _bundled_tesseract_path()
    if bundled:
        return str(bundled)
    found = shutil.which("tesseract")
    if found:
        return found
    candidates = _WINDOWS_TESSERACT_CANDIDATES if sys.platform == "win32" else _MAC_TESSERACT_CANDIDATES
    for candidate in candidates:
        if Path(candidate).is_file():
            return candidate
    return None


def configure_tesseract() -> bool:
    """Configura pytesseract con la ruta encontrada. Devuelve True si lo encontró."""
    global _bundled_tessdata_dir
    bundled = _bundled_tesseract_path()
    if bundled:
        pytesseract.pytesseract.tesseract_cmd = str(bundled)
        bundled_dir = bundled.parent
        tessdata = bundled_dir / "tessdata"
        _bundled_tessdata_dir = tessdata if tessdata.is_dir() else None
        if sys.platform.startswith("linux"):
            # Las .so de Tesseract/Leptonica que viajan empaquetadas junto
            # al binario no están en el loader path del sistema del usuario.
            existing = os.environ.get("LD_LIBRARY_PATH", "")
            lib_path = str(bundled_dir)
            if lib_path not in existing.split(":"):
                os.environ["LD_LIBRARY_PATH"] = (
                    f"{lib_path}:{existing}" if existing else lib_path
                )
        return True

    _bundled_tessdata_dir = None
    path = locate_tesseract()
    if path:
        pytesseract.pytesseract.tesseract_cmd = path
        return True
    return False


class TesseractNotFoundError(RuntimeError):
    """Se necesita OCR pero no se encontró el ejecutable de Tesseract."""


class EncryptedPdfError(RuntimeError):
    """El PDF está protegido con una contraseña que no se pudo abrir."""


@dataclass
class PageResult:
    number: int
    used_ocr: bool


@dataclass
class ConversionResult:
    source: Path
    output: Path
    pages: list[PageResult]

    @property
    def ocr_pages(self) -> int:
        return sum(1 for p in self.pages if p.used_ocr)


def _page_has_native_text(page: fitz.Page) -> bool:
    text = page.get_text("text").strip()
    return len(text) >= MIN_NATIVE_CHARS


def _ocr_page(page: fitz.Page, lang: str) -> str:
    if not locate_tesseract():
        raise TesseractNotFoundError(
            "No se encontró Tesseract OCR, necesario para páginas escaneadas. "
            "Instalalo y volvé a intentar (ver instrucciones en README.md)."
        )
    pix = page.get_pixmap(dpi=OCR_DPI)
    img = Image.open(io.BytesIO(pix.tobytes("png")))
    config = f'--tessdata-dir "{_bundled_tessdata_dir}"' if _bundled_tessdata_dir else ""
    text = pytesseract.image_to_string(img, lang=lang, config=config)
    return text.strip()


def convert_pdf(
    pdf_path: Path,
    out_path: Path,
    ocr_lang: str = "spa+eng",
    progress_cb: Optional[Callable[[int, int], None]] = None,
) -> ConversionResult:
    """Convierte un PDF a Markdown y guarda el resultado en output_dir."""
    doc = fitz.open(pdf_path)
    if doc.needs_pass:
        # Muchos PDF oficiales están "cifrados" solo con restricciones de
        # impresión/edición pero sin contraseña de apertura: se abren con
        # clave vacía. Si eso falla, es una contraseña real que no tenemos.
        if not doc.authenticate(""):
            doc.close()
            raise EncryptedPdfError(
                f"'{pdf_path.name}' está protegido con contraseña y no se pudo abrir."
            )
    total = doc.page_count

    native_pages: list[int] = []
    ocr_pages: dict[int, str] = {}
    page_results: list[PageResult] = []

    for i, page in enumerate(doc):
        if _page_has_native_text(page):
            native_pages.append(i)
            page_results.append(PageResult(number=i + 1, used_ocr=False))
        else:
            ocr_pages[i] = _ocr_page(page, ocr_lang)
            page_results.append(PageResult(number=i + 1, used_ocr=True))
        if progress_cb:
            progress_cb(i + 1, total)

    # Markdown con estructura/tablas para las páginas con texto nativo.
    native_md: dict[int, str] = {}
    if native_pages:
        chunks = pymupdf4llm.to_markdown(doc, pages=native_pages, page_chunks=True)
        for chunk, page_no in zip(chunks, native_pages):
            native_md[page_no] = chunk["text"].strip()

    parts: list[str] = []
    for i in range(total):
        if i in native_md:
            parts.append(native_md[i])
        else:
            ocr_text = ocr_pages.get(i, "")
            if ocr_text:
                parts.append(ocr_text)
            # página vacía: se omite

    markdown = "\n\n".join(p for p in parts if p)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(markdown, encoding="utf-8")

    doc.close()
    return ConversionResult(source=pdf_path, output=out_path, pages=page_results)


def find_pdfs(folder: Path, recursive: bool = True) -> list[Path]:
    """Busca archivos PDF en `folder`, opcionalmente incluyendo subcarpetas."""
    glob = folder.rglob if recursive else folder.glob
    seen: dict[str, Path] = {}
    for pattern in ("*.pdf", "*.PDF"):
        for p in glob(pattern):
            seen[str(p)] = p
    return sorted(seen.values())


def output_path_for(pdf_path: Path, input_root: Path, output_root: Path) -> Path:
    """Calcula la ruta .md de salida, replicando la subcarpeta relativa al
    directorio de entrada (para no pisar archivos con el mismo nombre en
    distintas subcarpetas)."""
    try:
        rel_dir = pdf_path.parent.relative_to(input_root)
    except ValueError:
        rel_dir = Path(".")
    return output_root / rel_dir / (pdf_path.stem + ".md")
