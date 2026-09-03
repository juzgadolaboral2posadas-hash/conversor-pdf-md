# Conversor de PDF a Markdown

App de escritorio (Tkinter) que convierte todos los PDF de una carpeta —y sus
subcarpetas— a archivos `.md`. Detecta automáticamente si cada página tiene
texto nativo (lo extrae preservando títulos y tablas con `pymupdf4llm`) o si
es una página escaneada (le aplica OCR con Tesseract).

## Requisitos

- Python 3.10+
- [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) instalado en el sistema:
  - **macOS**: `brew install tesseract tesseract-lang`
  - **Windows**: instalador desde [UB-Mannheim/tesseract](https://github.com/UB-Mannheim/tesseract/wiki) (marcar el paquete de español al instalar)
  - **Linux (Debian/Ubuntu)**: `sudo apt install tesseract-ocr tesseract-ocr-spa`

## Uso en modo desarrollo

```bash
python3 -m venv venv
source venv/bin/activate   # en Windows: venv\Scripts\activate
pip install -r requirements.txt
python3 app.py
```

## Compilar el ejecutable (por sistema operativo)

`PyInstaller` **no compila de forma cruzada**: hay que correrlo en cada
sistema operativo para obtener su ejecutable (un Mac genera el `.app`, un
Windows genera el `.exe`, un Linux genera el binario ELF).

En cada máquina, con Tesseract ya instalado (ver arriba):

```bash
python3 -m venv venv
source venv/bin/activate        # en Windows: venv\Scripts\activate
pip install -r requirements.txt
pip install pyinstaller
pyinstaller --noconfirm build.spec
```

El resultado queda en `dist/`:
- **macOS**: `dist/ConversorPDFaMD.app`
- **Windows**: `dist/ConversorPDFaMD/ConversorPDFaMD.exe`
- **Linux**: `dist/ConversorPDFaMD/ConversorPDFaMD`

Tesseract **no** se empaqueta dentro del ejecutable: cada máquina que use la
app compilada necesita tenerlo instalado por separado (ver Requisitos). El
resto de las dependencias de Python sí quedan incluidas en el ejecutable.

## Build automático en la nube (GitHub Actions)

El repo incluye `.github/workflows/build.yml`, que compila automáticamente
para macOS, Windows y Linux en los servidores de GitHub. Se dispara:

- Al pushear un tag con formato `v*` (ej. `git tag v1.0 && git push origin v1.0`)
- Manualmente desde la pestaña **Actions** del repo en GitHub (botón "Run workflow")

Los tres ejecutables quedan disponibles para descargar como *artifacts* del
workflow, sin necesidad de tener las tres computadoras.
