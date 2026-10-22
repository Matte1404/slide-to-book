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
  - slide non spiegate da una citazione mirata: coperte solo da intervalli ampi (più di 4 slide distinte
    nella stessa parentesi o in parentesi attaccate; i passi di un'animazione Beamer contano una volta),
    da citazioni con meno di 5 parole intorno per slide (3 per le slide quasi vuote; una formula vale
    3 parole, un blocco di codice una per riga; una frase che finisce con "[...]:" prende anche l'elenco,
    la tabella o la formula che segue), o solo da riepiloghi (In breve, Formule e notazione, ...) e dalle
    voci di "Dove l'hai visto"
  - molte slide con del testo coperte solo dalla sezione "Slide di servizio"
  - paragrafi che parlano di lezione, docente o esame senza citare una fonte T o E
  - segmenti delle trascrizioni mai citati
  - esercizi citati nel libro ma assenti dal catalogo (--esercizi)
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
from collections import Counter, defaultdict
from pathlib import Path

BRACKET = re.compile(r"\[([^\[\]\n]{3,400})\](?!\()")
ID_PART = re.compile(r"^\s*([STEX][0-9][0-9A-Za-z-]*)\s*(?:,\s*(.*?))?\s*$")
TS = r"\d{1,2}:\d{2}(?::\d{2})?"
POS_TS = re.compile(r"^(" + TS + r")(?:\s*[-–—]\s*(" + TS + r"))?$")
POS_UNIT = re.compile(r"^(slides?|pag(?:\.|ina|ine|g\.)?|pp?\.|par(?:\.|agrafo|agrafi)?)\s*(.+)$", re.I)
# una parola chiave intera ("esempio 3" non è l'esercizio "empio 3") o un'abbreviazione col punto ("dom.A")
POS_EX = re.compile(r"^(?:(?:es|dom|q)\.|(?:es(?:ercizi[oi]?)?|domand[ae]|quesit[oi])(?![^\W\d_]))\s*(.+)$", re.I)
TAGS = ["INTEGRAZIONE", "DA VERIFICARE", "DISCREPANZA", "FUORI SLIDE",
        "SOLUZIONE GENERATA", "ESCLUSO DAL DOCENTE"]
TAG_RE = re.compile(r"\[(" + "|".join(TAGS) + r")\b[^\]]*\]")
# affermazioni su ciò che è stato detto a lezione o chiesto all'esame (non semplici menzioni del docente)
CLAIM = re.compile(r"(?i)(\b(?:detto|spiegato|sottolineato|ripetuto|visto|svolto|fatto) a lezione\b|"
                   r"\b(?:il|la)\s+(?:docente|prof\w*\.?)(?:\s+\w+){0,2}\s+(?:ha|aveva)\s+"
                   r"(?:detto|sottolineato|insistito|ripetuto|spiegato|raccomandato|chiesto|avvertito)\b|"
                   r"\b(?:uscit|chiest)[oaie]\s+(?:all['’]|agli\s+|in\s+|nell['’]|negli\s+)(?:esam|appell))")
TE_CITE = re.compile(r"\[[^\]]*\b[TEX][0-9][0-9A-Za-z-]*\s*,")
# una citazione che copre più slide distinte di così non dice quale slide spiega quale frase
WIDE = 4
PER_SLIDE = 5  # parole intorno a una citazione per ogni slide citata (meno, se la slide stessa ne ha meno)
MIN_WORDS = 3  # ma almeno queste: anche un diagramma senza testo estratto va spiegato
FORMULA_WORDS = 3  # una formula o un pezzo di codice nel testo vale come tre parole
SERVICE = "slide di servizio"  # titolo della sezione delle appendici con titoli, indici, ringraziamenti
VISUAL = "(lettura visiva)"    # le note aggiunte da visual.py note
ADJACENT = re.compile(r"(?:[\s;,.:·–—-]|\b(?:e|ed|o)\b)*", re.I)  # fra due citazioni che vanno lette insieme
LOW_TEXT = 40                  # caratteri sotto cui una slide è quasi vuota (come in extract_sources.py)
# sezioni del modello di capitolo che riassumono o rimandano: una slide citata solo lì non è spiegata
NEUTRAL = ("In breve", "Prerequisiti", "Formule e notazione", "Concetti chiave", "Errori comuni",
           "Domande di autoverifica", "Collegamenti")


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
    """Etichetta di un esercizio senza spazi e punti, tranne il punto prima di una cifra: "2. b" -> "2b",
    "2.2" e "II.1" restano."""
    return re.sub(r"\s|(?<!\w)\.|\.(?!\d)", "", label.lower())


ROMAN = r"x{0,3}(?:ix|iv|v?i{0,3})"


NUMBER = r"(?:\d+|(?=[ivx])%s)" % ROMAN  # numero arabo o romano (non vuoto)


def ex_part(label):
    """L'esercizio senza la lettera della parte: "2b" -> "2", "2.2b" -> "2.2", "iib" -> "ii", "ii.1" resta,
    "a1b" -> "a1". "3bis" resta: è un altro esercizio."""
    m = re.fullmatch(r"(%s(?:\.\d+)*)[a-h]?" % NUMBER, label)
    return m.group(1) if m else re.sub(r"(?<=\d)[a-h]$", "", label)


def ex_number(label):
    """Il numero dell'esercizio intero: "2.2b" -> "2", "ii.1" -> "ii", "a1b" -> "a1", "3bis" resta."""
    m = re.fullmatch(r"(%s)(?:\.\d+)*[a-h]?" % NUMBER, label)
    return m.group(1) if m else ex_part(label)


def natural(loc):
    """Ordine "01.md:9" prima di "01.md:12"."""
    return [int(s) if s.isdigit() else s for s in re.split(r"(\d+)", loc)]


def solo_match(sid, value):
    """Un valore di --solo vale per l'ID uguale e per quelli che lo continuano senza un'altra cifra; una
    lettera sola o un valore che finisce con un trattino ("S1-", "E2024-") valgono come prefisso."""
    if len(value) == 1 or not value[-1].isalnum():
        return sid.startswith(value)
    return sid == value or (sid.startswith(value) and not sid[len(value)].isdigit())


def citation_words(f):
    """Il testo intorno alle citazioni di un file del libro: ({(riga, gruppo): parole}, righe di rimando,
    righe con DOMANDA DEL DOCENTE). I gruppi sono numerati come in scan().

    Le parole di un gruppo sono quelle fra il gruppo precedente e il successivo nello stesso paragrafo;
    righe vuote, titoli, voci di un elenco e righe di una tabella chiudono il paragrafo, così una voce
    non presta le sue parole a un'altra. Una formula conta FORMULA_WORDS parole, un blocco di codice una
    per riga. Una frase che finisce con una citazione e i due punti ("Le proprietà ACID [S03, slide 6]:")
    prende anche le parole dell'elenco, della tabella, della formula o del codice che la seguono.
    Le righe di rimando sono le voci di «Dove l'hai visto» di un esercizio: dicono dove trovarlo, non lo spiegano."""
    raw = f.read_text(encoding="utf-8-sig")
    raw_lines, text = raw.split("\n"), strip_code(raw)
    weight = defaultdict(list)  # riga -> (colonna, parole) di formule e codice che iniziano lì
    for m in re.finditer(r"```.*?```|\$\$.*?\$\$|`[^`\n]*`|\$[^$\n]+\$", raw, flags=re.S):
        n = FORMULA_WORDS
        if m.group(0).startswith("```"):
            n = max(FORMULA_WORDS, sum(1 for l in m.group(0).split("\n")[1:-1] if l.strip()))
        weight[raw.count("\n", 0, m.start())].append((m.start() - raw.rfind("\n", 0, m.start()) - 1, n))

    def words(k, line, a, b):
        return len(re.findall(r"[^\W\d_]{2,}", line[a:b])) + sum(n for c, n in weight.get(k, []) if a <= c < b)

    out, extra, refs, markers, section = {}, defaultdict(int), set(), set(), [0]
    lead, own, in_refs = None, False, False  # gruppo che introduce un blocco con ":"; ancora nel suo paragrafo;
    # dentro «Dove l'hai visto»

    def close():
        for j, g in enumerate(section[1::2]):
            out[g] = section[2 * j] + section[2 * j + 2]

    for k, line in enumerate(text.split("\n")):
        rl = raw_lines[k]
        blank = not rl.strip()
        heading = bool(line.strip() and re.match(r"^\s{0,3}#{1,6}\s", rl))
        item = bool(re.match(r"^\s*(?:[-*+]|\d+[.)])\s|^\s*\|", rl))
        cited = bool(BRACKET.search(line))
        if "DOMANDA DEL DOCENTE" in rl:
            markers.add(k + 1)
        if "dove l'hai visto" in rl.lower():
            in_refs = True
        elif blank or heading or not item:
            in_refs = False
        elif in_refs and cited:
            refs.add(k + 1)
        if lead is not None:  # l'elenco, la tabella, la formula o il codice introdotti dalla citazione
            own = own and not blank and not item  # finché il paragrafo continua, le sue parole contano già
            if heading or cited or not blank and not item and line.strip():
                lead = None
            elif not blank and not own:
                extra[lead] += words(k, line, 0, len(line))
        if blank or heading:
            close()
            section = [0]
            continue
        if item:  # una nuova voce o riga di tabella
            close()
            section = [0]
        group, end, pos = 0, None, 0
        for bm in BRACKET.finditer(line):
            if end is None or not ADJACENT.fullmatch(line[end:bm.start()]):
                group += 1
                section[-1] += words(k, line, pos, bm.start())
                section += [(k + 1, group), 0]
            pos = end = bm.end()
        section[-1] += words(k, line, pos, len(line))
        if group and line.rstrip().endswith(":"):
            lead, own = (k + 1, group), True
    close()
    for g, n in extra.items():
        out[g] = out.get(g, 0) + n
    return out, refs, markers


def book_files(path):
    p = Path(path)
    if p.is_file():
        return [p]
    return sorted(f for f in p.rglob("*.md")
                  if not any(part.startswith("_") for part in f.relative_to(p).parts))


def unit_numbers(info):
    """Numero di unità per fonti con numerazione (slide/pag/par)."""
    return len(info["labels"])


def slide_texts(fonti, sid):
    """Righe di testo di ogni slide (indici da 0) in _fonti/<ID>.md, senza gli avvisi dello script."""
    try:  # è solo per gli avvisi: un file illeggibile non deve fermare il controllo
        text = (Path(fonti) / (sid + ".md")).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}
    pages = {}
    for m in re.finditer(r"(?ms)^## \[%s, slide (\d+)\]\n(.*?)(?=^## \[|\Z)" % re.escape(sid), text):
        pages[int(m.group(1)) - 1] = [l.strip() for l in m.group(2).split("\n") if l.strip()
                                      and not l.startswith("⚠") and l.strip() != "(nessun testo estratto)"]
    return pages


def extracted(lines):
    """Il testo estratto dalla slide, senza le letture visive aggiunte dopo."""
    return " ".join(l for l in lines if not l.startswith(VISUAL))


def overlay_steps(pages):
    """Slide che ripetono la precedente aggiungendo qualcosa, come i passi di un'animazione Beamer:
    gli indici i per cui ogni parola della slide i-1 compare anche nella slide i (un \\pause dentro
    una riga allunga la riga invece di aggiungerne una). Una citazione a tutti i passi di
    un'animazione riguarda una slide sola, non un intervallo. Le letture visive non contano, perché
    ogni passo può averne una sua; per questo due slide quasi vuote con lo stesso titolo (due
    immagini diverse) contano come passi solo se la seconda aggiunge qualcosa."""
    words = {i: Counter(re.findall(r"\w+", extracted(ls).lower())) for i, ls in pages.items()}
    return {i for i in words if words.get(i - 1) and not words[i - 1] - words[i]
            and (sum(words[i].values()) > sum(words[i - 1].values())
                 or len(re.sub(r"\s", "", extracted(pages[i]))) >= LOW_TEXT)}


def distinct_slides(idxs, steps):
    """Slide distinte in una citazione: i passi di un'animazione contano con la slide da cui partono."""
    s = set(idxs)
    return sum(1 for i in s if not (i in steps and i - 1 in s))


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
    """Restituisce citazioni trovate: lista di (id, tipo, valore, file, riga, titolo, gruppo, servizio).
    Il gruppo riunisce le citazioni nella stessa parentesi o in parentesi separate solo da
    punteggiatura o da "e" ("[S01, slide 1-4]; [S01, slide 5-8]"): insieme sostengono la stessa frase.
    servizio dice se la citazione sta nella sezione "Slide di servizio", anche sotto un suo sottotitolo."""
    cites = []
    for f in files:
        raw = f.read_text(encoding="utf-8-sig")
        raw_lines = raw.split("\n")
        text = strip_code(raw)
        heading = f.stem
        service_level = 0
        for lineno, line in enumerate(text.split("\n"), 1):
            heading = heading_of(raw_lines[lineno - 1], line, heading)
            hm = re.match(r"^\s{0,3}(#{1,6})\s+(.*)", raw_lines[lineno - 1]) if line.strip() else None
            if hm:  # la sezione delle slide di servizio finisce al titolo successivo dello stesso livello
                if service_level and len(hm.group(1)) <= service_level:
                    service_level = 0
                if not service_level and SERVICE in hm.group(2).lower():
                    service_level = len(hm.group(1))
            group, end = 0, None
            for bm in BRACKET.finditer(line):
                if end is None or not ADJACENT.fullmatch(line[end:bm.start()]):
                    group += 1
                end = bm.end()
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
                        cites.append((pm.group(1), res[0], res[1], f, lineno, heading, (f, lineno, group),
                                      bool(service_level)))
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
    ap.add_argument("--solo", help="controlla solo queste fonti, separate da virgola (es. S01,S02,T01): utile per "
                    "consegnare una parte del corso. S1 vale anche per S1-01 e S1-02 ma non per S10, E2024-02 anche "
                    "per E2024-02a e E2024-02-sol, una lettera da sola (E) per tutte le fonti di quel tipo")
    args = ap.parse_args()
    prefixes = [x.strip() for x in args.solo.split(",") if x.strip()] if args.solo else None
    in_scope = (lambda sid: any(solo_match(sid, p) for p in prefixes)) if prefixes else (lambda sid: True)

    index_path = Path(args.fonti) / "_indice.json"
    if not index_path.exists():
        sys.exit("Indice non trovato: %s (esegui prima extract_sources.py)" % index_path)
    index = json.loads(index_path.read_text(encoding="utf-8"))
    if prefixes:  # un valore che non corrisponde a niente farebbe passare il controllo senza controllare nulla
        unmatched = [x for x in prefixes if not any(solo_match(sid, x) for sid in index)]
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
    exercises_cited = {}  # (ID, esercizio) -> prima posizione nel libro
    cited_ids = set()
    pages, steps = {}, {}
    precise = defaultdict(set)    # slide spiegate da almeno una citazione mirata con abbastanza testo intorno
    service = defaultdict(set)    # slide citate nella sezione delle slide di servizio
    wide_at = defaultdict(list)   # citazioni che non bastano a dire che una slide è spiegata: (posizione, slide)
    together = defaultdict(set)   # (gruppo, ID) -> slide citate insieme
    around = {}                   # file -> citation_words(file)
    told = defaultdict(float)     # (ID, slide) -> parole del libro attribuite alla slide
    told_at = defaultdict(list)   # (ID, slide) -> citazioni che le hanno date

    def steps_of(sid):
        if sid not in steps:
            pages[sid] = slide_texts(args.fonti, sid)
            steps[sid] = overlay_steps(pages[sid])
        return steps[sid]

    for sid, kind, value, f, lineno, heading, group, in_service in cites:
        if kind == "idx" and sid.startswith("S") and not in_service:
            together[(group, sid)].update(value)

    def first_of(i, slides, st):
        """La slide da cui parte l'animazione di cui i è un passo, fra quelle citate insieme."""
        while i in st and i - 1 in slides:
            i -= 1
        return i

    for sid, kind, value, f, lineno, heading, group, in_service in cites:
        cited_ids.add(sid)
        if kind == "es":
            exercises_cited.setdefault((sid, value), "%s:%d" % (f.name, lineno))
            continue
        if sid.startswith("S"):
            loc = "%s:%d" % (f.name, lineno)
            if in_service:
                service[sid].update(value)
            elif distinct_slides(together[(group, sid)], steps_of(sid)) > WIDE:
                wide_at[sid].append((loc, set(value)))
            else:
                if f not in around:
                    around[f] = citation_words(f)
                words, refs, markers = around[f]
                if lineno in markers:  # "DOMANDA DEL DOCENTE n. 5 [S05, slide 48]": la sezione risponde alla domanda
                    precise[sid].update(value)
                elif heading.startswith(NEUTRAL) or lineno in refs:  # riepiloghi e rimandi non spiegano
                    wide_at[sid].append((loc, set(value)))
                else:  # le parole intorno al gruppo, divise fra le slide distinte che cita
                    slides, st = together[(group, sid)], steps_of(sid)
                    firsts = {first_of(i, slides, st) for i in slides}
                    for i in set(value):
                        if i in firsts:
                            told[(sid, i)] += words.get(group[1:], 0) / float(len(firsts))
                        told_at[(sid, first_of(i, slides, st))].append((loc, {i}))
        for i in value:
            covered[sid].add(i)
            loc = "%s › %s" % (f.stem, heading) if heading != f.stem else f.stem
            if loc not in covered_at[sid][i]:
                covered_at[sid][i].append(loc)

    # una slide è spiegata se le sue citazioni hanno, tutte insieme, abbastanza parole intorno: PER_SLIDE,
    # meno se la slide stessa ne ha meno (letture visive comprese), ma almeno MIN_WORDS
    for (sid, first), uses in told_at.items():
        need = min(PER_SLIDE, max(MIN_WORDS, len(re.findall(r"[^\W\d_]{2,}", " ".join(pages[sid].get(first, []))))))
        for loc, idxs in uses:
            if told[(sid, first)] >= need:
                precise[sid].update(idxs)
            else:
                wide_at[sid].append((loc, idxs))

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
            unit = info["labels"][0].rsplit(" ", 1)[0]
            only_wide = sorted(got - precise[sid] - service[sid])
            # titoli, "Grazie", divisori di sezione hanno poco testo, e gli indici ripetuti a ogni sezione
            # hanno le stesse righe: conta solo le slide con del testo che non sta in altre slide di servizio
            texts = pages[sid] if sid in pages else slide_texts(args.fonti, sid)
            own = {i: {l for l in texts.get(i, []) if not l.startswith(VISUAL)} for i in service[sid]}
            only_service = sorted(i for i in service[sid] - precise[sid]
                                  if len(re.sub(r"\s", "", extracted(texts.get(i, [])))) >= LOW_TEXT
                                  and own[i] - set().union(*[own[j] for j in own if j != i]))
            report.append("%s: %d/%d %s coperte (%.0f%%)%s" % (sid, n - len(missing), n, unit,
                          100.0 * (n - len(missing)) / n,
                          ", %d non spiegate da una citazione mirata" % len(only_wide) if only_wide else ""))
            if only_wide:  # solo le citazioni che contengono le slide segnalate, una volta ciascuna
                places = sorted({loc for loc, idxs in wide_at[sid] if idxs & set(only_wide)}, key=natural)
                one = len(only_wide) == 1
                warnings.append("%s: %s %s %s solo da citazioni a più di %d slide, con poco testo intorno o in "
                                "riepiloghi e rimandi (%s%s): controlla che %s"
                                % (sid, unit, compress([i + 1 for i in only_wide]), "coperta" if one else "coperte",
                                   WIDE, ", ".join(places[:3]), " …" if len(places) > 3 else "",
                                   "sia spiegata e citala vicino al testo che la spiega" if one else
                                   "ognuna sia spiegata e citale vicino al testo che le spiega"))
            if len(only_service) > max(3, 0.25 * n):
                warnings.append("%s: %d %s su %d, con del testo, coperte solo da «Slide di servizio» (%s): "
                                "controlla che non abbiano contenuto da spiegare"
                                % (sid, len(only_service), unit, n, compress([i + 1 for i in only_service])))
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

            def in_book(sid, value):
                """Una parte citata ("2b", "2.2") vale per l'esercizio intero del catalogo ("2"), non il contrario:
                se il catalogo elenca 1a e 1b, citare l'esercizio 1 non basta per 1b."""
                whole = ex_number(value) == value
                return any(s == sid and (c == value or ex_part(c) == value or whole and ex_number(c) == value)
                           for s, c in exercises_cited)
            for sid, kind, value, f, lineno, heading, _, _ in catalog:
                if kind == "es" and in_scope(sid) and not in_book(sid, value):
                    errors.append("%s:%d esercizio [%s, es. %s] non compare nel libro"
                                  % (ex_path.name, lineno, sid, value))
            # lo script non può leggere il numero di un esercizio nel PDF, ma può confrontarlo con il catalogo
            # "es. 1a" e "es. 2c" sono parti degli esercizi 1 e 2; le soluzioni non sono nel catalogo
            listed = {(sid, value) for sid, kind, value, _, _, _, _, _ in catalog if kind == "es"}
            wholes = {(sid, ex_number(v)) for sid, v in listed}  # il catalogo elenca le parti: l'intero c'è

            def in_catalog(sid, value):
                return (sid, value) in wholes or any((sid, v) in listed for v in (value, ex_part(value), ex_number(value)))
            for (sid, value), where in sorted(exercises_cited.items()):
                if in_scope(sid) and not re.search(r"-sol\d*$", sid) and not in_catalog(sid, value):
                    warnings.append("%s esercizio [%s, es. %s] citato ma assente da %s: controlla il numero "
                                    "sul testo dell'esame o aggiungilo al catalogo" % (where, sid, value, ex_path.name))

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
