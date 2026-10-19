#!/usr/bin/env python3
"""Aiuti per la lettura visiva delle slide segnalate da extract_sources.py.

Tre comandi:

  todo    elenca, per ogni fonte, le slide segnalate che non hanno ancora una lettura visiva
          python3 visual.py todo --fonti dispensa/_fonti

  render  mette più pagine di un PDF in un'unica immagine (un "provino"), da guardare in una
          volta sola invece che pagina per pagina
          python3 visual.py render --pdf slide/lez02.pdf --pagine 14,15,24-26 --out provino.png

  note    aggiunge "(lettura visiva) …" sotto l'intestazione di una slide, in _fonti/ID.md
          python3 visual.py note --fonti dispensa/_fonti S02 15 "Diagramma: tre blocchi in serie …"

render usa pdftoppm (poppler) oppure PyMuPDF, e Pillow per comporre il provino; senza
Pillow lascia le singole immagini. Se le pagine del PDF sono già visibili nella
conversazione (un allegato in chat), guardale lì: render non serve.
"""

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

MARK = "(lettura visiva)"


def parse_pages(spec):
    pages = []
    for tok in spec.split(","):
        tok = tok.strip()
        m = re.fullmatch(r"(\d+)\s*-\s*(\d+)", tok)
        if m:
            pages.extend(range(int(m.group(1)), int(m.group(2)) + 1))
        elif tok.isdigit():
            pages.append(int(tok))
        elif tok:
            sys.exit("--pagine: \"%s\" non è un numero né un intervallo (es. 5,14-16)" % tok)
    return pages


def pymupdf():
    """Il modulo PyMuPDF, o None: dalla versione 1.24.3 si chiama pymupdf, il vecchio nome fitz è deprecato."""
    try:
        import pymupdf as mod
        return mod
    except ImportError:
        pass
    try:
        import fitz as mod
        return mod if hasattr(mod, "open") else None
    except ImportError:
        return None


def page_count(pdf):
    try:
        with pymupdf().open(pdf) as doc:
            return len(doc)
    except Exception:  # PyMuPDF assente o PDF illeggibile: si prova con pdfinfo
        pass
    if shutil.which("pdfinfo"):
        out = subprocess.run(["pdfinfo", pdf], capture_output=True, encoding="utf-8", errors="replace").stdout
        m = re.search(r"(?m)^Pages:\s+(\d+)", out)
        if m:
            return int(m.group(1))
    return None


def cmd_todo(args):
    pending_total = 0
    for f in sorted(Path(args.fonti).glob("*.md")):
        text = f.read_text(encoding="utf-8")
        sections = re.split(r"(?m)^(?=## \[)", text)
        pending = []
        for sec in sections:
            m = re.match(r"## \[([^,\]]+), ([^\]]+)\]", sec)
            if m and "⚠" in sec and MARK not in sec:
                pending.append(m.group(2).split()[-1])
        if pending:
            pending_total += len(pending)
            print("%s: %s" % (f.stem, ", ".join(pending)))
    print("Da guardare: %d" % pending_total if pending_total else "Nessuna slide segnalata senza lettura visiva.")


def render_pages(pdf, pages, dpi, tmp):
    """Una PNG per pagina, con pdftoppm o, in mancanza, PyMuPDF."""
    if shutil.which("pdftoppm"):
        images = []
        for p in pages:
            prefix = tmp / ("p%04d" % p)
            subprocess.run(["pdftoppm", "-png", "-r", str(dpi), "-f", str(p), "-l", str(p),
                            pdf, str(prefix)], check=True)
            images += sorted(tmp.glob("p%04d*.png" % p))
        return images
    fitz = pymupdf()
    if fitz is None:
        sys.exit("Serve pdftoppm (poppler) oppure PyMuPDF (pip install pymupdf). Se non puoi "
                 "installarli, guarda le pagine nel PDF allegato o chiedi all'utente uno screenshot.")
    images = []
    with fitz.open(pdf) as doc:
        for p in pages:
            out = tmp / ("p%04d.png" % p)
            doc[p - 1].get_pixmap(dpi=dpi).save(str(out))
            images.append(out)
    return images


def cmd_render(args):
    pages = parse_pages(args.pagine)
    n = page_count(args.pdf)
    if n is not None and any(p < 1 or p > n for p in pages):
        print("Il PDF ha %d pagine: ignoro %s" % (n, ", ".join(str(p) for p in pages if p < 1 or p > n)))
        pages = [p for p in pages if 1 <= p <= n]
    if not pages:
        sys.exit("Nessuna pagina da mostrare")
    tmp = Path(tempfile.mkdtemp(prefix="provino-"))
    try:
        images = render_pages(args.pdf, pages, args.dpi, tmp)
    except BaseException:  # anche sys.exit: la cartella temporanea non deve restare
        shutil.rmtree(str(tmp), ignore_errors=True)
        raise
    try:
        from PIL import Image, ImageDraw
    except ImportError:  # le immagini singole sono il risultato: la cartella resta
        print("Pillow non disponibile: immagini singole in %s" % tmp)
        return
    try:
        make_sheet(args, pages, images, Image, ImageDraw)
    finally:
        shutil.rmtree(str(tmp), ignore_errors=True)


def make_sheet(args, pages, images, Image, ImageDraw):
    """Compone il provino e lo salva in args.out."""
    ims = []
    for i in images:
        with Image.open(i) as im:
            ims.append(im.convert("RGB"))
    w = max(i.width for i in ims)
    h = max(i.height for i in ims) + 20
    cols = min(args.colonne, len(ims))
    rows = (len(ims) + cols - 1) // cols
    sheet = Image.new("RGB", (w * cols, h * rows), "white")
    draw = ImageDraw.Draw(sheet)
    for k, (page, im) in enumerate(zip(pages, ims)):
        x, y = (k % cols) * w, (k // cols) * h
        draw.text((x + 4, y + 3), "pagina %d" % page, fill="red")
        sheet.paste(im, (x, y + 20))
    sheet.save(args.out)
    print("Provino: %s (%d pagine, %dx%d px)" % (args.out, len(ims), sheet.width, sheet.height))


def cmd_note(args):
    path = Path(args.fonti) / (args.id + ".md")
    text = path.read_text(encoding="utf-8")
    head = re.search(r"(?m)^## \[%s, (?:slide|pag\.|par\.) %d\]\n" % (re.escape(args.id), args.slide), text)
    if not head:
        sys.exit("Intestazione della slide %d non trovata in %s" % (args.slide, path))
    i = head.end()
    while text[i:].startswith("⚠"):  # dopo gli avvisi dello script
        i = text.index("\n", i) + 1
    text = text[:i] + "%s %s\n" % (MARK, args.testo.strip()) + text[i:]
    path.write_text(text, encoding="utf-8")
    print("Nota aggiunta: %s, slide %d" % (args.id, args.slide))


def main():
    for stream in (sys.stdout, sys.stderr):  # console Windows (cp1252) con output su pipe
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("todo")
    t.add_argument("--fonti", required=True)
    r = sub.add_parser("render")
    r.add_argument("--pdf", required=True)
    r.add_argument("--pagine", required=True, help="es. 5,14-16")
    r.add_argument("--out", required=True)
    r.add_argument("--dpi", type=int, default=60, help="60 basta per il testo grande; 80-90 per formule")
    r.add_argument("--colonne", type=int, default=3)
    n = sub.add_parser("note")
    n.add_argument("--fonti", required=True)
    n.add_argument("id")
    n.add_argument("slide", type=int)
    n.add_argument("testo")
    args = ap.parse_args()
    {"todo": cmd_todo, "render": cmd_render, "note": cmd_note}[args.cmd](args)


if __name__ == "__main__":
    main()
