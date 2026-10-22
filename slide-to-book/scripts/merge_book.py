#!/usr/bin/env python3
"""Unisce i capitoli della dispensa in un unico file ed eventualmente lo converte.

Uso:
    python3 merge_book.py --capitoli dispensa/capitoli \\
        --extra dispensa/punti-da-verificare.md dispensa/copertura.md \\
        --out dispensa/dispensa-completa.md --titolo "Nome del corso" [--lingua it] [--pdf] [--docx] [--html]

- I capitoli sono presi in ordine di nome (00-, 01-, …, 99-), poi i file --extra.
- Tra un file e l'altro mette sempre una riga vuota: con un semplice `cat`, un file
  che non finisce con un a capo incolla il titolo del capitolo successivo alla sua
  ultima riga, e il capitolo sparisce dall'indice.
- Le conversioni usano pandoc. Per il PDF serve un motore LaTeX Unicode (xelatex,
  lualatex o tectonic); i caratteri di disegno degli alberi e i simboli matematici
  richiedono un font che li contenga (--font, --font-mono). Senza LaTeX il PDF si
  ricava dal DOCX con LibreOffice, se c'è, con le emoji sostituite da simboli (⭐ -> ★)
  e l'indice scritto nel testo; altrimenti viene saltato.
- L'HTML usa MathML: le formule si vedono anche senza internet.
- Produce i formati che l'ambiente permette e dice che cosa manca. Esce con codice 1
  solo se nessuno dei formati richiesti è stato prodotto.
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# candidati in ordine di preferenza: si sceglie quello installato a cui mancano meno caratteri
# (frecce, ⟨⟩, ≠, ∀, caratteri di disegno degli alberi…). STIX Two Text viene dopo perché su
# macOS è un font variabile, e XeTeX/tectonic non ne trovano il grassetto.
FONT_CANDIDATES = ["STIXGeneral", "DejaVu Serif", "Noto Serif", "STIX Two Text", "Palatino", "Cambria"]
MONO_CANDIDATES = ["Menlo", "DejaVu Sans Mono", "Noto Sans Mono", "Consolas", "Courier New"]
# Stelle, frecce, segni di spunta ed emoji spesso mancano nel font del testo, o ci sono solo nel
# tondo e spariscono nei titoli in grassetto. Nel PDF li disegna un font di simboli, lo stesso in
# tutti gli stili; le emoji a colori LaTeX non le sa disegnare e diventano simboli monocromatici.
SYMBOL_CANDIDATES = ["STIXGeneral", "DejaVu Sans", "Noto Sans Symbols 2", "Noto Sans Symbols",
                     "Apple Symbols", "Segoe UI Symbol", "Symbola"]
EMOJI = {"⭐": "★", "🎓": "▸", "✅": "✓", "❌": "✗", "📌": "▸", "💡": "▸", "👉": "▸", "❗": "!",
         "\ufe0f": ""}  # U+FE0F: selettore "versione emoji" (come in ⚠️), da togliere
TOC_TITLE = {"it": "Indice", "en": "Contents", "fr": "Table des matières", "es": "Índice", "de": "Inhalt"}


def used_chars(text):
    """Caratteri non ASCII del testo e del codice, separati (vanno in font diversi)."""
    code = "".join(re.findall(r"```.*?```", text, flags=re.S) + re.findall(r"`[^`\n]+`", text))
    prose = re.sub(r"```.*?```", " ", text, flags=re.S)
    prose = re.sub(r"`[^`\n]+`", " ", prose)
    prose = re.sub(r"\$\$.*?\$\$|\$[^$\n]+\$", " ", prose, flags=re.S)  # le formule usano il font matematico
    pick = lambda t: sorted({c for c in t if ord(c) > 127 and not c.isspace()})
    return pick(prose), pick(code)


def font_families(pattern):
    """Famiglie di font installate che corrispondono a un pattern di fc-list."""
    out = subprocess.run(["fc-list", pattern, "family"], capture_output=True,
                         encoding="utf-8", errors="replace").stdout
    return {f.strip() for line in out.splitlines() for f in line.split(",")}


def pick_font(chars, candidates):
    """Il candidato installato a cui mancano meno caratteri (a parità, il primo della lista).
    Senza fc-list, o se nessun candidato è installato, None: si usa il font predefinito di
    pandoc invece di indovinare un nome che potrebbe non esistere e far fallire LaTeX."""
    if not shutil.which("fc-list"):
        return None, []  # i caratteri mancanti li segnala LaTeX ("Missing character")
    families = font_families(":")
    installed = [c for c in candidates if c in families]
    if not installed:
        return None, chars
    every = font_families(":charset=" + (" ".join("%x" % ord(c) for c in chars) or "41"))
    for c in installed:
        if c in every:
            return c, []
    cover = {ch: font_families(":charset=%x" % ord(ch)) for ch in chars}  # uno per carattere: più lento
    missing = {c: [ch for ch in chars if c not in cover[ch]] for c in installed}
    best = min(installed, key=lambda c: (len(missing[c]), installed.index(c)))
    return best, missing[best]


def is_symbol(c):
    o = ord(c)
    return (0x2190 <= o <= 0x21FF or 0x2300 <= o <= 0x23FF or 0x25A0 <= o <= 0x27BF
            or 0x2900 <= o <= 0x2BFF or o == 0xFE0F or o >= 0x1F000)


def symbol_header(chars, missing):
    """Header LaTeX che fa disegnare simboli ed emoji a un font di simboli, in ogni stile.
    Restituisce (percorso del file .tex o None, font usato, caratteri ancora senza glifo)."""
    targets = sorted({c for c in chars if is_symbol(c) or c in missing})
    if not targets or not shutil.which("fc-list"):
        return None, None, []
    repl = {c: EMOJI.get(c, "•" if ord(c) >= 0x1F000 else c) for c in targets}
    shown = sorted({r for r in repl.values() if r})
    families = font_families(":")
    fonts = [f for f in SYMBOL_CANDIDATES if f in families]
    if not fonts:
        return None, None, shown
    cover = {ch: font_families(":charset=%x" % ord(ch)) for ch in shown}
    lacks = {f: [ch for ch in shown if f not in cover[ch]] for f in fonts}
    font = min(fonts, key=lambda f: (len(lacks[f]), fonts.index(f)))
    lines = ["% generato da merge_book.py: simboli ed emoji con un font di simboli, in tutti gli stili",
             "\\usepackage{newunicodechar}",
             "\\newfontfamily\\slbsimboli{%s}[BoldFont=%s,ItalicFont=%s,BoldItalicFont=%s]" % ((font,) * 4)]
    for c in targets:
        r = repl[c]
        # nelle formule il carattere resta com'è: lì lo disegna il font matematico
        lines.append("\\newunicodechar{%s}{\\ifmmode %s\\else{\\slbsimboli %s}\\fi}" % (c, c, r) if r
                     else "\\newunicodechar{%s}{}" % c)
    fd, path = tempfile.mkstemp(suffix=".tex", prefix="simboli-")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return path, font, lacks[font]


def merge(chapters_dir, extras, out, title, lang):
    files = sorted(p for p in Path(chapters_dir).glob("*.md") if not p.name.startswith("_"))
    files += [Path(e) for e in extras]
    missing = [str(f) for f in files if not f.is_file()]
    if missing:
        sys.exit("File non trovati: " + ", ".join(missing))
    parts = []
    if title:
        parts.append('---\ntitle: "%s"\nlang: %s\n---\n' % (title.replace('"', "'"), lang))
    for f in files:
        parts.append(f.read_text(encoding="utf-8-sig").strip("\n") + "\n")
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text("\n".join(parts), encoding="utf-8")
    return files


def latex_engine():
    return next((e for e in ("xelatex", "lualatex", "tectonic") if shutil.which(e)), None)


# emoji del piano base che i font di LibreOffice non hanno (⏳, ⛔, ✨...); ★ ✓ ✗ ▸ invece li hanno
BMP_EMOJI = ("\u231a\u231b\u23e9-\u23ec\u23f0\u23f3\u25fd\u25fe\u2614\u2615\u2648-\u2653\u267f\u2693\u26a1\u26aa"
             "\u26ab\u26bd\u26be\u26c4\u26c5\u26ce\u26d4\u26ea\u26f2\u26f3\u26f5\u26fa\u26fd\u2705\u270a\u270b\u2728"
             "\u274c\u274e\u2753-\u2755\u2757\u2795-\u2797\u27b0\u27bf\u2b1b\u2b1c\u2b50\u2b55")
EMOJI_CHAR = "(?:[\U0001F000-\U0001FFFF]|[%s])" % BMP_EMOJI
ATTRS = re.compile(r"\{\s*(?:-|(?:[#.][\w:-]+|[\w-]+=(?:\"[^\"]*\"|\S+))(?:\s+(?:[#.][\w:-]+|[\w-]+=(?:\"[^\"]*\"|\S+)))*)\s*\}\s*$")


def plain_symbols(text):
    """Emoji -> simboli che i font hanno: ⭐ -> ★ e così via (EMOJI); una sequenza (bandiera, tono della pelle,
    famiglia con U+200D) diventa un solo •, come ogni altra emoji."""
    text = re.sub("[\U0001F3FB-\U0001F3FF\U000E0020-\U000E007F\ufe0f]", "", text)  # toni, etichette, selettore
    text = re.sub("[\U0001F1E6-\U0001F1FF]{2}", "•", text)  # bandiere
    text = re.sub("(%s)(?:\u200d%s)+" % (EMOJI_CHAR, EMOJI_CHAR), r"\1", text)  # sequenze con U+200D
    for emoji, symbol in EMOJI.items():
        text = text.replace(emoji, symbol)
    return re.sub(EMOJI_CHAR, "•", text)


def toc_text(title):
    """Il titolo come testo di una voce dell'indice: link e note tolti, parentesi quadre protette
    (fuori da codice e formule), così la voce resta un collegamento solo."""
    title = re.sub(r"\[\]\{[^}]*\}", "", title)                 # ancore vuote
    title = re.sub(r"\[\^[^\]]*\]", "", title)                  # note a piè di pagina
    title = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", title)      # link: resta il testo
    parts = re.split(r"(`[^`]*`|\$[^$]*\$)", title)
    return "".join(p if i % 2 else re.sub(r"([\[\]])", r"\\\1", p) for i, p in enumerate(parts)).strip()


def office_markdown(src, out, lang):
    """Il Markdown unito preparato per LibreOffice. Le emoji diventano simboli che i suoi font hanno
    (⭐ -> ★): le emoji a colori nel PDF resterebbero spazi vuoti. L'indice è scritto nel testo, con un
    collegamento a ogni titolo di primo e secondo livello: LibreOffice senza interfaccia non aggiorna il campo
    dell'indice del DOCX e lo lascerebbe vuoto. I titoli tengono il loro identificatore (i rimandi interni
    restano validi); quelli che non ne hanno uno esplicito ricevono un'ancora in più."""
    lines = plain_symbols(Path(src).read_text(encoding="utf-8")).split("\n")
    start = lines.index("---", 1) + 1 if lines and lines[0] == "---" and "---" in lines[1:] else 0
    toc, fence = [], None  # fence: il segno che apre il blocco di codice in corso ("```", "~~~~"...)

    def anchor(k, level, title):
        m = ATTRS.search(title)
        ident = re.search(r"#([\w:-]+)", m.group(0)) if m else None
        text = title[:m.start()].rstrip() if m else title
        if ident:
            target = ident.group(1)
        else:
            target = "indice-%d" % (len(toc) + 1)
            if m:  # attributi senza identificatore: lo aggiungiamo lì
                title = text + " {#%s %s}" % (target, m.group(0).strip()[1:-1].strip())
            else:
                title = text + " []{#%s}" % target
        toc.append("%s- [%s](#%s)" % ("  " * (level - 1), toc_text(text), target))
        return title

    k = start
    while k < len(lines):
        line = lines[k]
        f = re.match(r"^ {0,3}(`{3,}|~{3,})", line)
        if fence:
            if f and f.group(1)[0] == fence[0] and len(f.group(1)) >= len(fence) and not line.strip(" `~"):
                fence = None
        elif f:
            fence = f.group(1)
        else:
            h = re.match(r"^(#{1,2})[ \t]+(.*?)(?:[ \t]+#+)?[ \t]*$", line)
            nxt = lines[k + 1] if k + 1 < len(lines) else ""
            s = re.match(r"^ {0,3}(={2,}|-{2,})[ \t]*$", nxt)
            plain = line.strip() and not re.match(r"^\s*(?:[-*+>|]|\d+[.)]|#)", line) and not line.startswith(("    ", "\t"))
            if h and h.group(2).strip():
                lines[k] = "%s %s" % (h.group(1), anchor(k, len(h.group(1)), h.group(2)))
            elif s and plain:  # titolo sottolineato con === o ---
                lines[k] = anchor(k, 1 if s.group(1)[0] == "=" else 2, line.strip())
                k += 1
        k += 1
    if toc:
        lines[start:start] = ["", "# %s" % TOC_TITLE.get(lang, TOC_TITLE["it"]), ""] + toc + [""]
    Path(out).write_text("\n".join(lines), encoding="utf-8")


def office_pdf(src, lang):
    """PDF ricavato da un DOCX con LibreOffice, quando manca un motore LaTeX. Il DOCX è preparato a parte,
    in una cartella temporanea, da office_markdown(). Restituisce (pdf o None, motivi)."""
    office = next((shutil.which(c) for c in ("soffice", "libreoffice") if shutil.which(c)), None)
    if not office:
        return None, ["nessun motore LaTeX (xelatex, lualatex, tectonic) né LibreOffice (soffice)"]
    tmp = Path(tempfile.mkdtemp(prefix="dispensa-pdf-"))
    try:
        prepared = tmp / Path(src).name
        office_markdown(src, prepared, lang)
        docx, warnings = convert(prepared, "docx", None, None, out=tmp / (Path(src).stem + ".docx"), toc=False)
        if not docx:
            return None, ["il DOCX da convertire non è stato prodotto"] + warnings
        # un profilo di LibreOffice a parte: non si blocca se LibreOffice è già aperto
        cmd = [office, "-env:UserInstallation=" + (tmp / "profilo").as_uri(), "--headless",
               "--convert-to", "pdf", "--outdir", str(tmp), str(Path(docx).resolve())]
        try:
            proc = subprocess.run(cmd, capture_output=True, encoding="utf-8", errors="replace", timeout=900)
            detail = (proc.stderr or proc.stdout).strip()[-500:]
        except subprocess.TimeoutExpired:
            detail = "non ha finito entro 15 minuti"
        made = tmp / (Path(docx).stem + ".pdf")
        if not made.is_file():
            return None, ["LibreOffice: " + (detail or "nessun PDF prodotto")]
        target = Path(src).with_suffix(".pdf")
        shutil.move(str(made), str(target))
        return target, []
    finally:
        shutil.rmtree(str(tmp), ignore_errors=True)


def convert(src, fmt, font, font_mono, header=None, out=None, toc=True, lang=None):
    """Converte con pandoc. Restituisce (file prodotto o None, righe di avviso o motivi dell'errore)."""
    if not shutil.which("pandoc"):
        return None, ["pandoc non trovato: per PDF, DOCX e HTML serve pandoc (il Markdown unito è pronto)"]
    out = out or Path(src).with_suffix("." + fmt)
    cmd = ["pandoc", str(src), "-o", str(out)] + (["--toc", "--toc-depth=2"] if toc else []) + [
           # elenchi e titoli subito dopo una riga di testo, senza riga vuota in mezzo, come li
           # accettano GitHub e gli editor: senza queste estensioni pandoc li fonde nel paragrafo
           "-f", "markdown+tex_math_dollars+lists_without_preceding_blankline-blank_before_header"
                 "-implicit_figures"]
    if fmt == "pdf":
        cmd += ["--pdf-engine=" + latex_engine(), "-V", "geometry:margin=2.2cm", "-V", "documentclass=report",
                "-V", "colorlinks=true"]
        cmd += ["-V", "mainfont=" + font] if font else []
        cmd += ["-V", "monofont=" + font_mono] if font_mono else []
        cmd += ["-H", header] if header else []
    elif fmt == "html":
        # MathML: le formule si vedono anche senza internet (MathJax arriverebbe da una CDN a ogni apertura)
        cmd += ["--standalone", "--embed-resources", "--mathml"]
    if toc and fmt != "pdf" and lang in TOC_TITLE:  # nel PDF il titolo dell'indice lo mette LaTeX dalla lingua
        cmd += ["-M", "toc-title=" + TOC_TITLE[lang]]
    proc = subprocess.run(cmd, capture_output=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0 and fmt == "html" and "embed-resources" in proc.stderr:
        # pandoc precedente alla 2.19: l'opzione si chiamava --self-contained
        cmd[cmd.index("--embed-resources")] = "--self-contained"
        proc = subprocess.run(cmd, capture_output=True, encoding="utf-8", errors="replace")
    warnings = [l for l in proc.stderr.splitlines() if l.strip()]
    if proc.returncode != 0:
        return None, ["conversione fallita"] + warnings[-25:]
    return out, warnings


def main():
    for stream in (sys.stdout, sys.stderr):  # console Windows (cp1252) con output su pipe
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--capitoli", required=True, help="cartella dei capitoli")
    ap.add_argument("--extra", nargs="*", default=[], help="file da aggiungere in fondo (appendici generate)")
    ap.add_argument("--out", required=True, help="file Markdown unito")
    ap.add_argument("--titolo", help="titolo del documento (metadati per pandoc)")
    ap.add_argument("--lingua", default="it", help="lingua della dispensa per pandoc (it, en, ...)")
    ap.add_argument("--pdf", action="store_true")
    ap.add_argument("--docx", action="store_true")
    ap.add_argument("--html", action="store_true")
    ap.add_argument("--font", help="font del testo (default: scelto in base ai caratteri usati)")
    ap.add_argument("--font-mono", help="font del codice (default: scelto in base ai caratteri usati)")
    args = ap.parse_args()

    files = merge(args.capitoli, args.extra, args.out, args.titolo, args.lingua)
    text = Path(args.out).read_text(encoding="utf-8")
    for f in files:  # ogni file deve aprire con un titolo di primo livello, o sparisce dall'indice
        first = next((l for l in f.read_text(encoding="utf-8-sig").splitlines() if l.strip()), "")
        if not first.startswith("# "):
            print("⚠ %s non inizia con un titolo di primo livello ('# ...'): non comparirà nell'indice" % f.name)
    print("Uniti %d file in %s (%d parole, %d titoli di primo livello)"
          % (len(files), args.out, len(text.split()), sum(1 for l in text.splitlines() if l.startswith("# "))))
    latex = latex_engine() if args.pdf else None
    if latex and not (args.font and args.font_mono):
        prose_chars, code_chars = used_chars(text)
        font, miss = (args.font, []) if args.font else pick_font(prose_chars, FONT_CANDIDATES)
        mono, miss_m = (args.font_mono, []) if args.font_mono else pick_font(code_chars, MONO_CANDIDATES)
        args.font, args.font_mono = font, mono
        print("Font per il PDF: %s (testo), %s (codice)" % (font or "predefinito", mono or "predefinito"))
        # le emoji della tabella EMOJI le disegna il font di simboli (vedi symbol_header): non sono un'assenza
        miss = [c for c in miss if c not in EMOJI]
        miss_m = [c for c in miss_m if c not in EMOJI]
        if miss or miss_m:
            print("  nel font del testo mancano: %s" % " ".join(sorted(set(miss + miss_m))))
    header = None
    if latex:
        prose_chars, _ = used_chars(text)
        _, miss = pick_font(prose_chars, [args.font]) if args.font else (None, prose_chars)
        header, sym_font, still = symbol_header(prose_chars, set(miss))
        if header:
            print("Simboli ed emoji nel PDF: font %s%s" % (sym_font, "; ancora senza glifo: " + " ".join(still)
                                                          if still else ""))
    made, failed = [], []
    try:
        convert_all(args, latex, header, made, failed)
    finally:  # anche se una conversione si interrompe, l'header temporaneo non resta in giro
        if header:
            os.remove(header)
    if failed:
        print("Prodotti: Markdown%s. Non prodotti: %s." % ("".join(", " + f.upper() for f in made),
                                                         ", ".join(f.upper() for f in failed)))
    sys.exit(1 if failed and not made else 0)


def convert_all(args, latex, header, made, failed):
    """Produce i formati richiesti, aggiungendoli a made o a failed."""
    for fmt in ("docx", "pdf", "html"):  # il DOCX prima: senza LaTeX il PDF si ricava da lì
        if getattr(args, fmt):
            via_office = fmt == "pdf" and not latex
            if via_office:
                out, warnings = office_pdf(args.out, args.lingua)
            else:
                out, warnings = convert(args.out, fmt, args.font, args.font_mono, header if fmt == "pdf" else None,
                                        lang=args.lingua)
            if out:
                made.append(fmt)
                missing = sorted(set(w for w in warnings if "Missing character" in w))
                # un PDF senza stelle o simboli non è un successo pieno: va detto, non nascosto
                note = (" (%d caratteri senza glifo: guarda il PDF)" % len(missing) if missing else
                        " (con LibreOffice dal DOCX: guarda che stelle e simboli si vedano)" if via_office else "")
                print("%s %s: %s%s" % ("⚠" if missing else "✓", fmt, out, note))
                for w in missing[:10]:
                    print("   " + w)
            else:
                failed.append(fmt)
                print("✗ %s non prodotto: %s" % (fmt, "\n   ".join(warnings) or "motivo sconosciuto"))


if __name__ == "__main__":
    main()
