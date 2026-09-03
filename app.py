"""App de escritorio: convierte todos los PDF de una carpeta a Markdown."""
from __future__ import annotations

import queue
import threading
import traceback
from pathlib import Path
from tkinter import Tk, StringVar, filedialog, ttk, END, messagebox

from converter import (
    EncryptedPdfError,
    TesseractNotFoundError,
    configure_tesseract,
    convert_pdf,
    find_pdfs,
    output_path_for,
)

LANG_OPTIONS = {
    "Español + Inglés": "spa+eng",
    "Español": "spa",
    "Inglés": "eng",
}


class App:
    def __init__(self, root: Tk):
        self.root = root
        root.title("Conversor de PDF a Markdown")
        root.geometry("640x520")
        root.minsize(560, 440)

        self.input_dir = StringVar()
        self.output_dir = StringVar()
        self.lang_label = StringVar(value="Español + Inglés")
        self.status = StringVar(value="Listo.")

        self.event_queue: "queue.Queue" = queue.Queue()
        self.worker: threading.Thread | None = None
        self.error_details: dict[str, str] = {}
        self.has_tesseract = configure_tesseract()

        self._build_ui()
        if not self.has_tesseract:
            self.status.set(
                "Aviso: no se encontró Tesseract OCR. Los PDF escaneados fallarán "
                "hasta que lo instales (ver README.md)."
            )
        self.root.after(100, self._poll_queue)

    # ---------- UI ----------
    def _build_ui(self) -> None:
        pad = {"padx": 10, "pady": 6}

        frm_in = ttk.Frame(self.root)
        frm_in.pack(fill="x", **pad)
        ttk.Label(frm_in, text="Carpeta con los PDF (incluye subcarpetas):").pack(anchor="w")
        row = ttk.Frame(frm_in)
        row.pack(fill="x")
        ttk.Entry(row, textvariable=self.input_dir).pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="Elegir…", command=self._choose_input).pack(side="left", padx=(6, 0))

        frm_out = ttk.Frame(self.root)
        frm_out.pack(fill="x", **pad)
        ttk.Label(frm_out, text="Carpeta de salida (.md):").pack(anchor="w")
        row2 = ttk.Frame(frm_out)
        row2.pack(fill="x")
        ttk.Entry(row2, textvariable=self.output_dir).pack(side="left", fill="x", expand=True)
        ttk.Button(row2, text="Elegir…", command=self._choose_output).pack(side="left", padx=(6, 0))

        frm_opts = ttk.Frame(self.root)
        frm_opts.pack(fill="x", **pad)
        ttk.Label(frm_opts, text="Idioma para OCR (páginas escaneadas):").pack(side="left")
        combo = ttk.Combobox(
            frm_opts, textvariable=self.lang_label, values=list(LANG_OPTIONS.keys()),
            state="readonly", width=20,
        )
        combo.pack(side="left", padx=(6, 0))

        self.btn_convert = ttk.Button(self.root, text="Convertir", command=self._start_conversion)
        self.btn_convert.pack(pady=(4, 6))

        self.progress = ttk.Progressbar(self.root, mode="determinate")
        self.progress.pack(fill="x", padx=10)

        ttk.Label(self.root, textvariable=self.status).pack(anchor="w", padx=10, pady=(4, 0))

        frm_log = ttk.Frame(self.root)
        frm_log.pack(fill="both", expand=True, padx=10, pady=10)
        self.log = ttk.Treeview(frm_log, columns=("estado",), show="tree headings", height=12)
        self.log.heading("#0", text="Archivo")
        self.log.heading("estado", text="Resultado")
        self.log.column("estado", width=180, anchor="w")
        self.log.pack(fill="both", expand=True)
        self.log.bind("<Double-1>", self._show_error_detail)

    # ---------- Acciones ----------
    def _choose_input(self) -> None:
        d = filedialog.askdirectory(title="Elegí la carpeta con los PDF")
        if d:
            self.input_dir.set(d)
            if not self.output_dir.get():
                self.output_dir.set(str(Path(d) / "md"))

    def _choose_output(self) -> None:
        d = filedialog.askdirectory(title="Elegí la carpeta de salida")
        if d:
            self.output_dir.set(d)

    def _start_conversion(self) -> None:
        if self.worker and self.worker.is_alive():
            return

        in_dir = Path(self.input_dir.get()).expanduser()
        out_dir_str = self.output_dir.get().strip()
        if not in_dir.is_dir():
            messagebox.showerror("Error", "Elegí una carpeta de entrada válida.")
            return
        out_dir = Path(out_dir_str).expanduser() if out_dir_str else in_dir / "md"

        pdfs = find_pdfs(in_dir, recursive=True)
        if not pdfs:
            messagebox.showinfo(
                "Sin archivos", "No se encontraron PDF en esa carpeta ni en sus subcarpetas."
            )
            return

        for row in self.log.get_children():
            self.log.delete(row)
        self.progress.configure(value=0, maximum=len(pdfs))
        self.status.set(f"Convirtiendo {len(pdfs)} archivo(s)…")
        self.btn_convert.configure(state="disabled")

        ocr_lang = LANG_OPTIONS[self.lang_label.get()]
        self.worker = threading.Thread(
            target=self._run_batch, args=(pdfs, in_dir, out_dir, ocr_lang), daemon=True
        )
        self.worker.start()

    def _run_batch(
        self, pdfs: list[Path], in_dir: Path, out_dir: Path, ocr_lang: str
    ) -> None:
        for pdf in pdfs:
            label = str(pdf.relative_to(in_dir))
            out_path = output_path_for(pdf, in_dir, out_dir)
            try:
                result = convert_pdf(pdf, out_path, ocr_lang=ocr_lang)
                if result.ocr_pages:
                    msg = f"OK ({result.ocr_pages} pág. con OCR)"
                else:
                    msg = "OK"
                self.event_queue.put(("item", label, msg, None))
            except TesseractNotFoundError as exc:
                self.event_queue.put(("item", label, "ERROR (falta Tesseract)", str(exc)))
            except EncryptedPdfError as exc:
                self.event_queue.put(("item", label, "ERROR (protegido)", str(exc)))
            except Exception as exc:
                traceback.print_exc()
                self.event_queue.put(("item", label, "ERROR", str(exc)))
            self.event_queue.put(("tick", None, None, None))
        self.event_queue.put(("done", str(out_dir), None, None))

    def _show_error_detail(self, _event) -> None:
        item = self.log.focus()
        if not item:
            return
        detail = self.error_details.get(item)
        if detail:
            messagebox.showerror("Detalle del error", detail)

    def _poll_queue(self) -> None:
        try:
            while True:
                kind, a, b, c = self.event_queue.get_nowait()
                if kind == "item":
                    item_id = self.log.insert("", END, text=a, values=(b,))
                    if c:
                        self.error_details[item_id] = c
                elif kind == "tick":
                    self.progress.configure(value=self.progress["value"] + 1)
                elif kind == "done":
                    self.status.set(f"Listo. Archivos .md en: {a}")
                    self.btn_convert.configure(state="normal")
        except queue.Empty:
            pass
        self.root.after(100, self._poll_queue)


def main() -> None:
    root = Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
