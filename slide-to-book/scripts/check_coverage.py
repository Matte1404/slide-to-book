#!/usr/bin/env python3
"""Controlla copertura e citazioni della dispensa.

Uso:
    python3 check_coverage.py --fonti dispensa/_fonti --libro dispensa/capitoli \\
        [--esercizi dispensa/esercizi.md] [--copertura dispensa/copertura.md]

Errori (codice di uscita 1):
  - unità delle fonti S (slide) mai citate nel libro
  - citazioni a ID inesistenti, a posizioni che non esistono o in formato non riconosciuto
  - esercizi del catalogo (--esercizi) mai citati nel libro
  - esami (fonti E) mai citati
Avvisi:
  - paragrafi che parlano di lezione, docente o esame senza citare una fonte T o E
  - segmenti delle trascrizioni mai citati
Stampa l'inventario dei tag; con --copertura scrive la tabella slide -> sezione
(senza parentesi quadre, così non conta come citazione).

Il testo tra backtick e nei blocchi di codice viene ignorato: gli esempi di
formato nella legenda non contano come citazioni.
"""

import argparse
import bisect
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

BRACKET = re.compile(r"\[([^\[\]\n]{3,400})\](?!\()")
ID_PART = re.compile(r"^\s*([STEX][0-9][0-9A-Za-z-]*)\s*(?:,\s*(.*?))?\s*$")
TS = r"\d{1,2}:\d{2}(?::\d{2})?"
POS_TS = re.compile(r"^(" + TS + r")(?:\s*[-–—]\s*(" + TS + r"))?$")
POS_UNIT = re.compile(r"^(slides?|pag(?:\.|ina|ine|g\.)?|pp?\.|par(?:\.|agrafo|agrafi)?)\s*(.+)$", re.I)
POS_EX = re.compile(r"^(?:es(?:\.|ercizio|ercizi)?|domanda|dom\.|quesito|q\.)\s*(.+)$", re.I)
TAGS = ["INTEGRAZIONE", "DA VERIFICARE", "DISCREPANZA", "FUORI SLIDE",
        "SOLUZIONE GENERATA", "ESCLUSO DAL DOCENTE"]
TAG_RE = re.compile(r"\[(" + "|".join(TAGS) + r")\b[^\]]*\]")
# affermazioni su ciò che è stato detto a lezione o chiesto all'esame (non semplici menzioni del docente)
CLAIM = re.compile(r"(?i)(\b(?:detto|spiegato|sottolineato|ripetuto|visto|svolto|fatto) a lezione\b|"
                   r"\b(?:il|la)\s+(?:docente|prof\w*\.?)(?:\s+\w+){0,2}\s+(?:ha|aveva)\s+"
                   r"(?:detto|sottolineato|insistito|ripetuto|spiegato|raccomandato|chiesto|avvertito)\b|"
                   r"\b(?:uscit|chiest)[oaie]\s+(?:all['’]|agli\s+|in\s+|nell['’]|negli\s+)(?:esam|appell))")
TE_CITE = re.compile(r"\[[^\]]*\b[TEX][0-9][0-9A-Za-z-]*\s*,")


def strip_code(text):
    """Sostituisce codice e formule con spazi, mantenendo i numeri di riga.

    Le formule contengono intervalli come $[S1, S2]$ che non sono citazioni."""
    blank = lambda m: re.sub(r"[^\n]", " ", m.group(0))
    text = re.sub(r"```.*?```", blank, text, flags=re.S)
    text = re.sub(r"\$\$.*?\$\$", blank, text, flags=re.S)
    text = re.sub(r"`[^`\n]*`", blank, text)
    return re.sub(r"\$[^$\n]+\$", blank, text)


def heading_of(raw_line, stripped_line, current):
    """Titolo di sezione corrente. Il titolo si legge dalla riga originale (con il codice),
    ma solo se la riga non è dentro un blocco di codice (lì la riga ripulita è vuota)."""
    hm = re.match(r"^\s{0,3}#{1,6}\s+(.*)", raw_line)
    if hm and stripped_line.strip():
        return re.sub(r"[⭐*`]|\s+$", "", hm.group(1)).strip() or current
    return current


def parse_numbers(s):
    nums = []
    for tok in re.split(r"\s*(?:,|\be\b)\s*", s.strip()):
        if not tok:
            continue
        m = re.fullmatch(r"(\d+)\s*[-–—]\s*(\d+)", tok)
        if m:
            a, b = int(m.group(1)), int(m.group(2))
            if b < a or b - a > 1000:
                return None
            nums.extend(range(a, b + 1))
        elif tok.isdigit():
            nums.append(int(tok))
        else:
            return None
    return nums or None


def ts_seconds(ts):
    parts = [int(x) for x in ts.split(":")]
    if len(parts) == 2:
        return parts[0] * 60 + parts[1]
    return parts[0] * 3600 + parts[1] * 60 + parts[2]


def compress(nums):
    nums = sorted(set(nums))
    out, i = [], 0
    while i < len(nums):
        j = i
        while j + 1 < len(nums) and nums[j + 1] == nums[j] + 1:
            j += 1
        out.append(str(nums[i]) if i == j else "%d-%d" % (nums[i], nums[j]))
        i = j + 1
    return ", ".join(out)


def compress_labels(idxs, labels):
    idxs = sorted(set(idxs))
    out, i = [], 0
    while i < len(idxs):
        j = i
        while j + 1 < len(idxs) and idxs[j + 1] == idxs[j] + 1:
            j += 1
        out.append(labels[idxs[i]] if i == j else "%s–%s" % (labels[idxs[i]], labels[idxs[j]]))
        i = j + 1
    return ", ".join(out)


def norm_ex(label):
    return re.sub(r"[\s.]", "", label.lower())


def book_files(path):
    p = Path(path)
    if p.is_file():
        return [p]
    return sorted(f for f in p.rglob("*.md")
                  if not any(part.startswith("_") for part in f.relative_to(p).parts))


def unit_numbers(info):
    """Numero di unità per fonti con numerazione (slide/pag/par)."""
    return len(info["labels"])


def check_citation(src_id, pos, index, where, errors):
    """Valida una citazione. Restituisce (tipo, valore) per la copertura, oppure None."""
    info = index.get(src_id)
    if info is None:
        errors.append("%s citazione [%s, %s]: ID %s non presente nel registro" % (where, src_id, pos, src_id))
        return None
    if not pos:
        errors.append("%s citazione [%s] senza posizione: aggiungi slide, minuto, paragrafo o esercizio"
                      % (where, src_id))
        return None
    unit = info["unit"]
    m = POS_EX.match(pos)
    if m:
        if src_id[0] not in "EX":
            errors.append("%s citazione [%s, %s]: per una fonte %s usa la posizione (slide, minuto, par.)"
                          % (where, src_id, pos, src_id[0]))
            return None
        return ("es", norm_ex(re.split(r"[,(]", m.group(1))[0]))
    m = POS_TS.match(pos)
    if m:
        if unit != "ts":
            errors.append("%s citazione [%s, %s]: %s non ha timestamp (usa %s)"
                          % (where, src_id, pos, src_id, info["labels"][0].split()[0] + " N"))
            return None
        if any(t and t.count(":") != 2 for t in m.groups()):
            # "00:50" può voler dire 50 minuti o 50 secondi: le intestazioni sono sempre ore:minuti:secondi
            errors.append("%s citazione [%s, %s]: scrivi ore:minuti:secondi come nelle intestazioni "
                          "di _fonti/ (per esempio 00:42:10)" % (where, src_id, pos))
            return None
        secs = [ts_seconds(m.group(1))] + ([ts_seconds(m.group(2))] if m.group(2) else [])
        for s in secs:
            if s > info["last_seconds"] + 60:
                errors.append("%s citazione [%s, %s]: la trascrizione finisce a %s"
                              % (where, src_id, pos, info["labels"][-1]))
                return None
        starts = info["seconds"]
        lo = max(bisect.bisect_right(starts, secs[0]) - 1, 0)
        hi = max(bisect.bisect_right(starts, secs[-1]) - 1, 0)
        return ("idx", list(range(lo, hi + 1)))
    m = POS_UNIT.match(pos)
    if m:
        kind = m.group(1).lower()
        kind = "par" if kind.startswith("par") else "page"
        if unit == "ts":
            errors.append("%s citazione [%s, %s]: %s usa timestamp (es. 00:42:10)" % (where, src_id, pos, src_id))
            return None
        if (kind == "par") != (unit == "par"):
            expected = info["labels"][0].rsplit(" ", 1)[0]
            errors.append("%s citazione [%s, %s]: %s è numerata per '%s'" % (where, src_id, pos, src_id, expected))
            return None
        nums = parse_numbers(m.group(2))
        if nums is None:
            errors.append("%s citazione [%s, %s]: numeri non riconosciuti" % (where, src_id, pos))
            return None
        n = unit_numbers(info)
        bad = [x for x in nums if x < 1 or x > n]
        if bad:
            errors.append("%s citazione [%s, %s]: %s ha solo %d %s" % (where, src_id, pos, src_id, n,
                          info["labels"][0].rsplit(" ", 1)[0]))
            return None
        return ("idx", [x - 1 for x in nums])
    errors.append("%s citazione [%s, %s]: posizione non riconosciuta (formati: 'slide 14', 'pag. 3', "
                  "'par. 27', '00:42:10', 'es. 2b')" % (where, src_id, pos))
    return None


def scan(files, index, errors):
    """Restituisce citazioni trovate: lista di (id, tipo, valore, file, riga, titolo)."""
    cites = []
    for f in files:
        raw = f.read_text(encoding="utf-8-sig")
        raw_lines = raw.split("\n")
        text = strip_code(raw)
        heading = f.stem
        for lineno, line in enumerate(text.split("\n"), 1):
            heading = heading_of(raw_lines[lineno - 1], line, heading)
            for bm in BRACKET.finditer(line):
                for part in bm.group(1).split(";"):
                    pm = ID_PART.match(part)
                    where = "%s:%d" % (f.name, lineno)
                    if not pm:
                        if re.match(r"\s*[STEX][0-9][\w-]*\b", part, re.I) or (";" in bm.group(1) and part.strip()):
                            errors.append("%s [%s]: citazione in formato non riconosciuto (usa [ID, posizione])"
                                          % (where, part.strip()))
                        continue
                    res = check_citation(pm.group(1), (pm.group(2) or "").strip(), index, where, errors)
                    if res:
                        cites.append((pm.group(1), res[0], res[1], f, lineno, heading))
    return cites


def claims_without_source(files):
    warnings = []
    for f in files:
        text = strip_code(f.read_text(encoding="utf-8-sig"))
        lineno, legend_level = 1, 0
        for para in re.split(r"(\n\s*\n)", text):
            # la legenda spiega che cosa significano le etichette ("uscito all'esame", ...) e
            # l'intestazione "Fonti" non può avere citazioni: non sono affermazioni da verificare.
            # La legenda va dal suo titolo al titolo successivo dello stesso livello o superiore.
            for marks, h in re.findall(r"(?m)^\s{0,3}(#{1,6})\s+(.*)$", para):
                if legend_level and len(marks) <= legend_level:
                    legend_level = 0
                if not legend_level and h.strip().lower().startswith(("legenda", "come usare")):
                    legend_level = len(marks)
            in_legend = legend_level > 0
            # i titoli non sono affermazioni: li togliamo lasciando le righe al loro posto
            body = re.sub(r"(?m)^\s{0,3}#{1,6}\s.*$", "", para)
            body = re.sub(r"(?m)^\s*>\s*\*\*(?:Fonti|Priorità):\*\*.*$", "", body)
            m = CLAIM.search(body) if body.strip() and not in_legend else None
            if m and not TE_CITE.search(body):
                snippet = re.sub(r"\s+", " ", body.strip())[:90]
                warnings.append("%s:%d \"%s…\" (parla di \"%s\" senza citare una fonte T, E o X)"
                                % (f.name, lineno + body[:m.start()].count("\n"), snippet, m.group(1)))
            lineno += para.count("\n")
    return warnings


def tag_inventory(files):
    """Per ogni tag: lista di (file:riga, posizione leggibile "capitolo › sezione", testo del tag)."""
    inv = defaultdict(list)
    for f in files:
        heading = f.stem
        raw = f.read_text(encoding="utf-8-sig")
        raw_lines = raw.split("\n")
        for lineno, line in enumerate(strip_code(raw).split("\n"), 1):
            heading = heading_of(raw_lines[lineno - 1], line, heading)
            for m in TAG_RE.finditer(line):
                where = "%s › %s" % (f.stem, heading) if heading != f.stem else f.stem
                # il testo del tag va preso dalla riga originale: strip_code cancella i `codici` e le formule
                # (la lunghezza della riga non cambia, quindi gli stessi indici valgono)
                text = raw_lines[lineno - 1][m.start():m.end()]
                inv[m.group(1)].append(("%s:%d" % (f.name, lineno), where, text))
    return inv


def write_tag_report(path, inv):
    """Appendice "Punti da verificare", generata: lo studente sa dove guardare."""
    order = ["DA VERIFICARE", "DISCREPANZA", "SOLUZIONE GENERATA", "FUORI SLIDE",
             "ESCLUSO DAL DOCENTE", "INTEGRAZIONE"]
    lines = ["# Punti da verificare", "",
             "Generata da check_coverage.py: dove compaiono i tag della dispensa, raggruppati per tipo.", ""]
    for tag in order:
        items = inv.get(tag, [])
        if not items:
            continue
        lines += ["## %s (%d)" % (tag, len(items)), ""]
        seen = []
        for _, where, text in items:
            entry = where if text == "[%s]" % tag else "%s: %s" % (where, text.strip("[]"))
            if entry not in seen:
                seen.append(entry)
        lines += ["- " + e for e in seen] + [""]
    Path(path).write_text("\n".join(lines), encoding="utf-8")


# sezioni di riepilogo del modello di capitolo: una slide citata lì è "ricordata", non spiegata
SUMMARY_HEADINGS = ("In breve", "Prerequisiti", "Formule e notazione", "Concetti chiave", "Errori comuni",
                    "Domande di autoverifica", "Domande del docente", "Collegamenti")


def explaining(locs):
    """Le sezioni che spiegano la slide; i riepiloghi solo se non c'è altro."""
    main = [l for l in locs if not l.split(" › ")[-1].startswith(SUMMARY_HEADINGS)]
    return main or locs


def write_coverage(path, index, covered_at, in_scope=lambda sid: True):
    lines = ["# Copertura delle slide", "",
             "Generata da check_coverage.py: per ogni slide, le sezioni della dispensa che la spiegano.", ""]
    for sid in sorted(k for k in index if k.startswith("S") and in_scope(k)):
        info = index[sid]
        labels = info["labels"]
        lines += ["## %s: %s" % (sid, Path(info["file"]).name), "",
                  "| %s | Dove è spiegata |" % labels[0].rsplit(" ", 1)[0].capitalize(), "|---|---|"]
        rows = []
        for i in range(len(labels)):
            locs = covered_at[sid].get(i)
            where = " · ".join(explaining(locs)) if locs else "⚠ NON COPERTA"
            if rows and rows[-1][2] == where and rows[-1][1] == i - 1:
                rows[-1][1] = i
            else:
                rows.append([i, i, where])
        for a, b, where in rows:
            num = str(a + 1) if a == b else "%d–%d" % (a + 1, b + 1)
            lines.append("| %s | %s |" % (num, where))
        lines.append("")
    Path(path).write_text("\n".join(lines), encoding="utf-8")


def main():
    for stream in (sys.stdout, sys.stderr):  # console Windows (cp1252) con output su pipe
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fonti", required=True, help="cartella _fonti con _indice.json")
    ap.add_argument("--libro", required=True, help="cartella dei capitoli o file unico della dispensa")
    ap.add_argument("--esercizi", help="catalogo degli esercizi (esercizi.md)")
    ap.add_argument("--copertura", help="file in cui scrivere la tabella slide -> sezione")
    ap.add_argument("--tag-report", help="file in cui scrivere l'appendice dei punti da verificare")
    ap.add_argument("--solo", help="controlla solo le fonti i cui ID iniziano con questi valori, separati "
                    "da virgola (es. S01,S02,T01): utile per consegnare una parte del corso")
    args = ap.parse_args()
    prefixes = [x.strip() for x in args.solo.split(",") if x.strip()] if args.solo else None
    in_scope = (lambda sid: any(sid.startswith(p) for p in prefixes)) if prefixes else (lambda sid: True)

    index_path = Path(args.fonti) / "_indice.json"
    if not index_path.exists():
        sys.exit("Indice non trovato: %s (esegui prima extract_sources.py)" % index_path)
    index = json.loads(index_path.read_text(encoding="utf-8"))
    if prefixes:  # un valore che non corrisponde a niente farebbe passare il controllo senza controllare nulla
        unmatched = [x for x in prefixes if not any(sid.startswith(x) for sid in index)]
        if unmatched:
            sys.exit("--solo: nessuna fonte corrisponde a %s (ID nell'indice: %s)"
                     % (", ".join(unmatched), ", ".join(sorted(index))))
        print("Controllo limitato a: %s" % ", ".join(sorted(sid for sid in index if in_scope(sid))))
    files = book_files(args.libro)
    if not files:
        sys.exit("Nessun file .md trovato in %s" % args.libro)

    errors, warnings = [], []
    cites = scan(files, index, errors)

    covered = defaultdict(set)
    covered_at = defaultdict(lambda: defaultdict(list))
    exercises_cited = set()
    cited_ids = set()
    for sid, kind, value, f, lineno, heading in cites:
        cited_ids.add(sid)
        if kind == "es":
            exercises_cited.add((sid, value))
            continue
        for i in value:
            covered[sid].add(i)
            loc = "%s › %s" % (f.stem, heading) if heading != f.stem else f.stem
            if loc not in covered_at[sid][i]:
                covered_at[sid][i].append(loc)

    report = []
    for sid in sorted(index):
        if not in_scope(sid):
            continue
        info = index[sid]
        n = len(info["labels"])
        got = covered[sid]
        if sid.startswith("S"):
            missing = [i + 1 for i in range(n) if i not in got]
            if missing:
                errors.append("%s (%s): %s mai citate: %s" % (sid, Path(info["file"]).name,
                              info["labels"][0].rsplit(" ", 1)[0], compress(missing)))
            report.append("%s: %d/%d %s coperte (%.0f%%)" % (sid, n - len(missing), n,
                          info["labels"][0].rsplit(" ", 1)[0], 100.0 * (n - len(missing)) / n))
        elif sid.startswith("T"):
            missing = [i for i in range(n) if i not in got]
            report.append("%s: %d/%d segmenti citati (%.0f%%)" % (sid, n - len(missing), n,
                          100.0 * (n - len(missing)) / n))
            if missing:
                warnings.append("%s: segmenti mai citati (logistica? spiegazioni perse?): %s"
                                % (sid, compress_labels(missing, info["labels"])))
        elif sid.startswith("E") and sid not in cited_ids and not re.search(r"-sol\d*$", sid):
            errors.append("%s (%s): esame mai citato nella dispensa" % (sid, Path(info["file"]).name))

    if args.esercizi:
        ex_path = Path(args.esercizi)
        if not ex_path.exists():
            errors.append("catalogo esercizi non trovato: %s" % ex_path)
        else:
            catalog = scan([ex_path], index, errors)
            for sid, kind, value, f, lineno, heading in catalog:
                if kind == "es" and in_scope(sid) and (sid, value) not in exercises_cited:
                    errors.append("%s:%d esercizio [%s, es. %s] non compare nel libro"
                                  % (ex_path.name, lineno, sid, value))

    warnings += claims_without_source(files)
    inv = tag_inventory(files)

    print("== Controllo dispensa ==")
    print("Fonti: %d · File del libro: %d · Citazioni valide: %d" % (len(index), len(files), len(cites)))
    print("\nERRORI (%d)" % len(errors))
    for e in errors:
        print("  ✗ " + e)
    print("\nAVVISI (%d)" % len(warnings))
    for w in warnings:
        print("  ! " + w)
    print("\nCOPERTURA")
    for r in report:
        print("  " + r)
    print("\nTAG")
    if not inv:
        print("  nessuno")
    for tag in TAGS:
        if inv.get(tag):
            locs = inv[tag]
            print("  [%s] ×%d: %s%s" % (tag, len(locs), ", ".join(l[0] for l in locs[:12]),
                                        " …" if len(locs) > 12 else ""))

    if args.copertura:
        write_coverage(args.copertura, index, covered_at, in_scope)
        print("\nTabella di copertura scritta in %s" % args.copertura)
    if args.tag_report:
        write_tag_report(args.tag_report, inv)
        print("Appendice dei punti da verificare scritta in %s" % args.tag_report)

    if errors:
        print("\nEsito: ✗ %d errori: correggi e riesegui." % len(errors))
        sys.exit(1)
    print("\nEsito: ✓ nessun errore%s." % (" (controlla gli avvisi)" if warnings else ""))


if __name__ == "__main__":
    main()
