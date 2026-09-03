# Conversor de PDF a Markdown

App de escritorio (Tkinter) que convierte todos los PDF de una carpeta —y sus
subcarpetas— a archivos `.md`. Detecta automáticamente si cada página tiene
texto nativo (lo extrae preservando títulos y tablas con `pymupdf4llm`) o si
es una página escaneada (le aplica OCR con Tesseract).

## Requisitos

- Python 3.10+ (solo para correrlo desde código fuente o compilarlo; los
  ejecutables ya compilados no lo necesitan).
- [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) instalado en el sistema:
  - **macOS**: `brew install tesseract tesseract-lang`
  - **Windows**: instalador desde [UB-Mannheim/tesseract](https://github.com/UB-Mannheim/tesseract/wiki) (marcar el paquete de español al instalar)
  - **Linux (Debian/Ubuntu)**: `sudo apt install tesseract-ocr tesseract-ocr-spa`

> Los ejecutables de **Windows y Linux** generados por el workflow de GitHub
> Actions ya traen Tesseract empaquetado (binario + datos de español/inglés):
> el usuario final los descomprime y corre la app directo, sin instalar nada
> de lo anterior. Este requisito solo aplica si corrés `app.py` desde código
> fuente, si compilás vos mismo con `pyinstaller` sin el paso de empaquetado
> del workflow, o para **macOS** (que sigue necesitando `brew install
> tesseract` — ver "Empaquetado sin instalación" más abajo).

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

Compilando así (solo `pyinstaller build.spec`), Tesseract **no** queda
empaquetado: cada máquina que use el ejecutable necesita tenerlo instalado
aparte (ver Requisitos). El resto de las dependencias de Python sí quedan
incluidas.

### Empaquetado sin instalación (Windows y Linux)

Para que el ejecutable no dependa de que el usuario instale Tesseract, hay
que copiar el binario de Tesseract (y sus datos de idioma) dentro de una
carpeta `tesseract-bin/` al lado del ejecutable generado. La app lo detecta
solo si la encuentra ahí. El workflow de GitHub Actions (ver abajo) ya hace
esto automáticamente — es la forma recomendada de generar estas versiones.
Para hacerlo a mano:

- **Windows**, con Tesseract instalado (`choco install tesseract`):
  ```powershell
  $dest = "dist\ConversorPDFaMD\tesseract-bin"
  New-Item -ItemType Directory -Force -Path $dest, "$dest\tessdata"
  Copy-Item "C:\Program Files\Tesseract-OCR\tesseract.exe" $dest
  Copy-Item "C:\Program Files\Tesseract-OCR\*.dll" $dest
  # copiar eng.traineddata y spa.traineddata a $dest\tessdata
  ```
- **Linux**, con Tesseract instalado (`sudo apt install tesseract-ocr`): copiar
  el binario más las `.so` específicas de Tesseract/Leptonica (con `ldd`) a
  `dist/ConversorPDFaMD/tesseract-bin/`, y los `.traineddata` a su subcarpeta
  `tessdata/`. El script exacto está en `.github/workflows/build.yml`.

> **Limitación conocida en Linux**: a diferencia de Windows, no existe un
> binario de Linux 100% portable entre distribuciones — depende de la
> versión de glibc y otras librerías del sistema. El paquete se genera en
> Ubuntu (vía GitHub Actions) y funciona bien en Ubuntu/Debian recientes;
> en distribuciones muy distintas (Alpine, distros muy viejas) podría no
> arrancar, y ahí sí haría falta instalar Tesseract con el gestor de
> paquetes de esa distro.

## Build automático en la nube (GitHub Actions)

El repo incluye `.github/workflows/build.yml`, que compila automáticamente
para macOS, Windows y Linux en los servidores de GitHub, empaquetando
Tesseract en las versiones de Windows y Linux (ver arriba). Se dispara:

- Al pushear un tag con formato `v*` (ej. `git tag v1.0 && git push origin v1.0`)
- Manualmente desde la pestaña **Actions** del repo en GitHub (botón "Run workflow")

Los tres ejecutables quedan disponibles para descargar como *artifacts* del
workflow, sin necesidad de tener las tres computadoras. Los de Windows y
Linux ya son autocontenidos: se descomprimen y se ejecutan directo.
