#!/usr/bin/env python3
"""Estrae il testo delle fonti di un corso in file Markdown numerati e citabili.

Uso:
    python3 extract_sources.py --out dispensa/_fonti \\
        S01=slide/lez01.pdf T01=trascrizioni/lez01.txt E2023-06=esami/giugno23.pdf

Il prefisso dell'ID decide come viene diviso il file:
    S  slide         una sezione per slide/pagina       -> [S01, slide 14]
    T  trascrizione  blocchi con timestamp, se presenti  -> [T01, 00:42:10]
                     altrimenti paragrafi numerati       -> [T01, par. 27]
    E  esame         una sezione per pagina             -> [E2023-06, pag. 2]
    X  altro         una sezione per pagina/paragrafo   -> [X01, pag. 4]

Formati: .pdf .pptx .docx .txt .md .srt .vtt; le immagini vengono registrate e
segnalate per la lettura visiva.

Un unico file con le trascrizioni di più lezioni si passa con il solo prefisso:
    python3 extract_sources.py --out dispensa/_fonti T=trascrizioni.docx
Lo script lo divide sui titoli di lezione ("Lezione 3", "Lez. 3 - 12/03",
"Lecture 3", "# Lezione del 12 marzo") o, se non ce ne sono, dove i timestamp
ripartono da zero, e crea T01, T02, ...: il numero viene dal titolo quando c'è,
così T03 corrisponde alla lezione 3.

Per ogni fonte scrive <out>/<ID>.md e aggiorna <out>/_indice.json (usato da
check_coverage.py). Rilancialo con nuovi file per aggiungerli all'indice.
I file già estratti non vengono sovrascritti senza --force, perché possono
contenere trascrizioni visive aggiunte a mano.

Con molti file conviene --lista elenco.txt (una coppia ID=FILE per riga).

Il modo più semplice è una cartella del corso con le sottocartelle slide/,
trascrizioni/ (o registrazioni/), esami/ e, se serve, altro/:
    python3 extract_sources.py --out dispensa/_fonti --corso cartella-del-corso
Lo script assegna gli ID da solo (numeri delle lezioni dai nomi dei file, date
degli appelli dai nomi degli esami, soluzioni riconosciute da "sol" nel nome),
scrive l'elenco in dispensa/elenco.txt ed estrae tutto. Segnala i file audio e
video, che vanno trascritti prima, e quelli che non sa classificare. Rilanciato dopo
aver aggiunto file, lascia a ogni fonte già estratta il suo ID. Per correggere un ID
modifica l'elenco, cancella _fonti/<vecchio ID>.md e rilancia con --lista dispensa/elenco.txt.

Dipendenze: nessuna per PPTX, DOCX e testo. Per i PDF basta uno fra pdftotext
(poppler), PyMuPDF, pypdf e pdfplumber; usa il primo che trova.
"""

import argparse
import functools
import hashlib
import json
import os
import posixpath
import re
import shutil
import subprocess
import sys
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

ID_RE = re.compile(r"^[STEX][0-9][0-9A-Za-z-]*$")
KIND_BY_PREFIX = {"S": "slide", "T": "trascrizione", "E": "esame", "X": "altro"}
LOW_TEXT = 40          # caratteri non-spazio sotto cui una slide va guardata visivamente
PARA_TARGET = 700      # lunghezza indicativa di un paragrafo numerato
PARA_MAX = 1400
BLOCK_TARGET = 600     # lunghezza indicativa di un blocco con timestamp
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".heic", ".tif", ".tiff", ".bmp"}

# ---------------------------------------------------------------- cartella del corso

# nomi delle sottocartelle (prima parola, senza numeri iniziali) -> prefisso dell'ID
FOLDER_KIND = {
    "S": {"slide", "slides", "lucidi", "presentazioni"},
    "T": {"trascrizioni", "trascrizione", "registrazioni", "sbobinature", "sbobine", "lezioni-audio",
          "transcripts", "transcriptions", "recordings", "audio", "video"},
    "E": {"esami", "esame", "appelli", "compiti", "prove", "temi", "tracce", "exams", "exam"},
    "X": {"altro", "programma", "esercitazioni", "esercizi", "formulari", "materiale", "dispense", "appunti",
          "extra", "other"},
}
AUDIO_EXT = {".mp3", ".m4a", ".wav", ".aac", ".ogg", ".flac", ".mp4", ".mov", ".mkv", ".webm", ".avi"}
TEXT_EXT = {".pdf", ".pptx", ".docx", ".txt", ".md", ".srt", ".vtt"} | IMAGE_EXT
SYSTEM_FILES = {"thumbs.db", "desktop.ini"}
# "sol", "soluzioni", "correzione", "svolto" come parole intere: "Energia_solare.pdf" non è una soluzione
SOL_WORD = re.compile(r"(?<![a-z])(?:sol|soluz[a-z]*|solutions?|risoluzion[ei]|correzion[ei]|svolt[oaie]"
                      r"|svolgiment[oi])(?![a-z])", re.I)
MONTHS = {m: i for i, names in enumerate([
    ("gennaio", "gen", "january", "jan"), ("febbraio", "feb", "february"), ("marzo", "mar", "march"),
    ("aprile", "apr", "april"), ("maggio", "mag", "may"), ("giugno", "giu", "june", "jun"),
    ("luglio", "lug", "july", "jul"), ("agosto", "ago", "august", "aug"),
    ("settembre", "set", "sett", "september", "sep", "sept"), ("ottobre", "ott", "october", "oct"),
    ("novembre", "nov", "november"), ("dicembre", "dic", "december", "dec")], 1) for m in names}


def natural_key(path):
    return [int(s) if s.isdigit() else s.lower() for s in re.split(r"(\d+)", Path(path).as_posix())]


def folder_kind(name):
    """Tipo di una cartella dal nome: "slide", "2_Slides", "Slide-del-corso", "esami vecchi"."""
    s = re.sub(r"^[\d\s._-]+", "", name.lower())
    for word in (s, re.split(r"[\s._-]+", s)[0]):  # prima il nome intero ("lezioni-audio"), poi la prima parola
        kind = next((k for k, names in FOLDER_KIND.items() if word in names), None)
        if kind:
            return kind
    return None


# mesi per esteso, cercati anche lontano dall'anno; le abbreviazioni ("set", "mar") solo accanto a un anno
FULL_MONTHS = {w: n for w, n in MONTHS.items() if len(w) > 4 or w in ("june", "july")}
MONTH_WORDS = "|".join(sorted(MONTHS, key=len, reverse=True))
# una data all'inizio del nome, con l'ora se c'è: non è il numero della lezione. "12-03-2025 Lezione 4",
# "2025.03.12_lez4", "2025-03-03 10-31-02" (OBS), "12 marzo 2025"; non "01_12-03-2025" (lezione 1, poi la data)
LEADING_DATE = re.compile(
    r"^(?:\d{1,2}[._-]\d{1,2}[._-](?:\d{4}|\d{2}(?![._-]\d))|\d{4}[._-]?\d{2}[._-]?\d{2}"
    r"|\d{1,2}[\s._-]*(?:%s)[\s._-]*(?:\d{4}|\d{2}))"
    r"(?:[\s._T-]+\d{1,2}[._h-]\d{2}(?:[._-]\d{2})?)?(?=[\s._-]|$)[\s._-]*" % MONTH_WORDS, re.I)
# l'ultimo numero di una data ("Registrazione 12-03-2025"): non è il numero della lezione
NOT_DATE = r"(?!\d)(?![._-]\d{1,2}[._-](?:\d{4}|\d{2}(?![._-]\d))(?!\d))"


def file_number(path):
    """Numero della lezione nel nome del file: "03_intro.pdf", "lez03.txt", "Lezione 3.docx", "Slide 03.pdf",
    "12-03-2025 Lezione 4.pdf" (la data iniziale non conta). "Esercitazione 1.pdf" non ha un numero di lezione."""
    stem = LEADING_DATE.sub("", path.stem)
    m = re.match(r"0*(\d{1,3})(?=[\s._-]|$)", stem)
    if m:
        return int(m.group(1))
    m = re.search(r"(?<![a-z])(?:lez(?:ione)?|lecture|lesson|lec|l|slides?|trascrizione|registrazione|sbobina"
                  r"(?:tura)?|transcript|week|settimana|cap(?:itolo)?|chapter|unit)[\s._-]*0*(\d{1,3})" + NOT_DATE,
                  stem, re.I)
    return int(m.group(1)) if m else None


def numbered_ids(prefix, items, modules, use_modules=None):
    """ID per una lista di (file, modulo). S01, S02, ... dal numero di lezione nel nome del file, così
    S03 e T03 sono la stessa lezione; i file senza numero vanno in coda e due file con lo stesso
    numero prendono una lettera (S04a, S04b). Se i numeri ripartono in ogni modulo (sottocartella):
    S1-01, S2-01, ..., con il numero del modulo preso dall'elenco ordinato `modules`, comune a slide
    e trascrizioni; use_modules=True la impone, per allineare le trascrizioni alle slide.
    Restituisce (ID, criterio, numerazione per modulo usata)."""
    nums = [file_number(f) for f, _ in items]
    known = [n for n in nums if n is not None]
    if use_modules is None:
        use_modules = len(set(known)) < len(known) and len({g for _, g in items}) > 1
    if use_modules and None not in nums:
        ids = [("%s%d-%02d" % (prefix, modules.index(g) + 1, n)) if g else "%s%02d" % (prefix, n)
               for (_, g), n in zip(items, nums)]
        if len(set(ids)) == len(ids):
            return ids, "modulo (sottocartella) e numero dal nome del file", True
    if not known:
        return ["%s%02d" % (prefix, i) for i in range(1, len(items) + 1)], "in ordine di nome", False
    ids, top, seen = [], max(known), {}
    for (f, _), n in zip(items, nums):
        if n is None:
            top += 1
            ids.append("%s%02d" % (prefix, top))
        elif nums.count(n) > 1:
            seen[n] = seen.get(n, 0) + 1
            ids.append("%s%02d%s" % (prefix, n, "abcdefghijklmnopqrstuvwxyz"[seen[n] - 1]))
        else:
            ids.append("%s%02d" % (prefix, n))
    how = ["numeri dai nomi dei file"]
    if None in nums:
        how.append("SENZA NUMERO, messi in coda: " + ", ".join(f.name for (f, _), n in zip(items, nums) if n is None))
    if len(set(known)) < len(known):
        how.append("STESSO NUMERO, distinti con una lettera")
    return ids, "; ".join(how), False


def academic_year(s):
    """(primo anno, match) di un anno accademico nel nome ("2024-25", "2023_2024"), o None."""
    for m in re.finditer(r"(?<!\d)(20\d{2})\s*[._/-]\s*(20\d{2}|\d{2})(?!\d)", s):
        if int(m.group(2)) % 100 == (int(m.group(1)) + 1) % 100:
            return int(m.group(1)), m
    return None


def exam_date(path):
    """(anno, mese) dal nome del file di un esame, o (anno, None), o None."""
    s = path.stem.lower()
    m = (re.search(r"(?<!\d)(20\d{2})(0[1-9]|1[0-2])[0-3]\d(?!\d)", s)  # 20250616
         or re.search(r"(20\d{2})[\s._-]?(0[1-9]|1[0-2])(?!\d)", s))
    if m:
        return int(m.group(1)), int(m.group(2))
    m = re.search(r"(?<!\d)(\d{1,2})[\s._-](\d{1,2})[\s._-](20\d{2}|\d{2})(?!\d)", s)
    if m and 1 <= int(m.group(2)) <= 12:
        y = int(m.group(3))
        return (y if y > 99 else 2000 + y), int(m.group(2))
    words = sorted(MONTHS.items(), key=lambda kv: -len(kv[0]))
    for word, month in words:  # "June 12 2025", "Sept 1st, 2024": il numero dopo il mese è il giorno
        m = re.search(r"(?<![a-z])%s(?![a-z])[\s._-]+\d{1,2}(?:st|nd|rd|th)?[\s,._-]+(20\d{2})(?!\d)" % word, s)
        if m:
            return int(m.group(1)), month
    # 06-2025, 6-2025; non "Analisi 1 2024" o "appello_1_2024", dove la cifra è il numero del corso o dell'appello
    m = re.search(r"(?:(?<![\d.])(0[1-9]|1[0-2])[\s._-]|(?<![^\s_-])([1-9])[.-])(20\d{2})(?!\d)", s)
    if m:
        return int(m.group(3)), int(m.group(1) or m.group(2))
    far = lambda: next((n for w, n in words if w in FULL_MONTHS and re.search(r"(?<![a-z])%s(?![a-z])" % w, s)), None)
    ay = academic_year(s)
    if ay:  # anno accademico: da ottobre a dicembre il primo anno, da gennaio a settembre il secondo
        first, m = ay
        # un'abbreviazione vale solo accanto all'anno accademico, e non se è seguita da una lettera ("Set A")
        month = far() or next((n for w, n in words if re.search(r"(?<![a-z])%s(?![a-z])[\s._-]*$" % w, s[:m.start()])
                               or re.match(r"[\s._-]*%s(?![a-z])(?![\s._-]+(?:[a-z]|\d{1,2})(?![a-z\d]))" % w, s[m.end():])), None)
        return (first if month and month >= 10 else first + 1 if month else first), month
    for word, month in words:
        m = re.search(r"(?<![a-z])%s(?![a-z])[\s._-]*'?(20\d{2}|\d{2})(?!\d)" % word, s)
        if m:
            y = int(m.group(1))
            return (y if y > 99 else 2000 + y), month
    m = re.search(r"(?<!\d)(20\d{2})(?!\d)", s)
    return (int(m.group(1)), far()) if m else None


def exam_key(path):
    """Nome dell'esame senza le parole che indicano le soluzioni: abbina "giugno25_soluzioni" a "giugno25"."""
    return " ".join(w for w in re.split(r"[\s._-]+", SOL_WORD.sub(" ", path.stem.lower())) if w)


def exam_ids(files):
    """ID degli esami e delle soluzioni. Restituisce (lista di (ID, file), avvisi)."""
    notes = []
    tests = [f for f in files if not SOL_WORD.search(f.stem)]
    sols = [f for f in files if SOL_WORD.search(f.stem)]
    bases, undated = [], 0
    for f in tests:
        d = exam_date(f)
        if d:
            bases.append("E%d-%02d" % d if d[1] else "E%d" % d[0])
        else:  # senza data: E01, E02, ... annotati nell'elenco
            undated += 1
            bases.append("E%02d" % undated)
    out, seen = [], {}
    for f, base in zip(tests, bases):
        if bases.count(base) > 1:  # più appelli nello stesso mese: E2024-02a, E2024-02b
            seen[base] = seen.get(base, 0) + 1
            base += "abcdefghijklmnopqrstuvwxyz"[seen[base] - 1]
        out.append((base, f))
    for f in sols:
        # stesso nome dell'esame tolto "soluzioni"; altrimenti l'unico esame con la stessa data
        match = [i for i, t in out if exam_key(t) == exam_key(f)]
        if len(match) != 1:
            d = exam_date(f)
            base = ("E%d-%02d" % d if d[1] else "E%d" % d[0]) if d else None
            match = [i for i, t in out if base and re.fullmatch(re.escape(base) + "[a-z]?", i)]
        if len(match) != 1 and d and not d[1]:  # soluzioni con il solo anno: l'unico esame di quell'anno senza soluzioni
            ay = academic_year(f.stem.lower())
            years = {d[0]} | ({ay[0], ay[0] + 1} if ay else set())
            solved = {i[:-4] for i, _ in out if i.endswith("-sol")}
            match = [i for i, t in out if i not in solved
                     and re.fullmatch(r"E(?:%s)(?:-\d\d)?[a-z]?" % "|".join(map(str, years)), i)]
            if len(match) == 1:
                notes.append("%s: soluzioni abbinate a %s solo per l'anno, controlla" % (f.name, match[0]))
        if len(match) == 1:
            sid = match[0] + "-sol"
        else:
            d = exam_date(f)
            sid = (("E%d-%02d" % d if d[1] else "E%d" % d[0]) if d else "E00") + "-sol"
            notes.append("%s: soluzioni senza un esame corrispondente (%s), controlla l'ID" % (f.name, sid))
        n = 1
        while any(i == sid for i, _ in out):  # due file di soluzioni per lo stesso esame
            n += 1
            sid = re.sub(r"-sol\d*$", "-sol%d" % n, sid)
        out.append((sid, f))
    return out, notes


def scan_course(root):
    """Classifica i file di una cartella del corso. Restituisce (righe dell'elenco, avvisi)."""
    root = Path(root)
    found = {k: [] for k in FOLDER_KIND}  # tipo -> lista di (file, modulo)
    audio, unknown, skipped = [], [], []
    for f in sorted(root.rglob("*"), key=natural_key):
        rel = f.relative_to(root)
        if (not f.is_file() or f.name.lower() in SYSTEM_FILES
                or any(p.startswith((".", "_", "~")) or p == "dispensa" for p in rel.parts)):
            continue  # file nascosti, di blocco di Office (~$lez07.pptx), cartelle di lavoro
        # il tipo viene dalla prima cartella riconosciuta nel percorso (slide/modulo1/... o modulo1/slide/...);
        # le altre cartelle formano il modulo
        folders = rel.parts[:-1]
        pos = next((i for i, p in enumerate(folders) if folder_kind(p)), None)
        kind = folder_kind(folders[pos]) if pos is not None else None
        module = "/".join(folders[:pos] + folders[pos + 1:]) if pos is not None else ""
        ext = f.suffix.lower()
        if ext in AUDIO_EXT:
            audio.append(f)
        elif kind is None:
            unknown.append(f)
        elif ext not in TEXT_EXT:
            skipped.append(f)
        else:
            found[kind].append((f, module))
    modules = sorted({g for k in ("S", "T") for _, g in found[k] if g}, key=natural_key)
    lines = ["# Elenco preparato da extract_sources.py --corso %s" % root.as_posix(),
             "# Controllalo: S e T della stessa lezione dovrebbero avere lo stesso numero, gli esami la data giusta.",
             "# Per correggere un ID modificalo qui, cancella _fonti/<vecchio ID>.md se esiste,",
             "# e rilancia con --lista <questo file>.", ""]
    notes = []
    by_module = False
    if found["S"]:
        ids, how, by_module = numbered_ids("S", found["S"], modules)
        lines += ["# slide: %s" % how] + ["%s=%s" % (i, f.as_posix()) for i, (f, _) in zip(ids, found["S"])] + [""]
    if found["T"]:
        if len(found["T"]) == 1:
            lines += ["# trascrizioni: un solo file, diviso per lezione dallo script",
                      "T=%s" % found["T"][0][0].as_posix(), ""]
        else:
            ids, how, _ = numbered_ids("T", found["T"], modules, True if by_module else None)
            lines += ["# trascrizioni: %s" % how] + ["%s=%s" % (i, f.as_posix())
                                                     for i, (f, _) in zip(ids, found["T"])] + [""]
    if found["E"]:
        out, exam_notes = exam_ids([f for f, _ in found["E"]])
        notes += exam_notes
        nodate = [f.name for i, f in out if re.fullmatch(r"E\d\d", i)]
        lines += ["# esami: data dal nome del file; soluzioni (-sol) abbinate all'esame con lo stesso nome o data"
                  + ("; senza data (E01, ...): %s" % ", ".join(nodate) if nodate else "")]
        lines += ["%s=%s" % (i, f.as_posix()) for i, f in out] + [""]
    if found["X"]:
        lines += ["# altro"] + ["X%02d=%s" % (i, f.as_posix()) for i, (f, _) in enumerate(found["X"], 1)] + [""]
    # un audio che ha accanto la sua trascrizione (stesso nome) non va trascritto di nuovo
    transcribed = {f.stem.lower() for f, _ in found["T"]}
    for f in audio:
        if f.stem.lower() in transcribed:
            lines.append("# audio con la trascrizione già presente, ignorato: %s" % f.as_posix())
        else:
            lines.append("# da trascrivere prima (audio e video non sono supportati): %s" % f.as_posix())
    for f in unknown:
        lines.append("# da classificare (fuori da slide/, trascrizioni/, esami/, altro/): %s" % f.as_posix())
    for f in skipped:
        lines.append("# formato non supportato, ignorato: %s" % f.as_posix())
    to_transcribe = [f for f in audio if f.stem.lower() not in transcribed]
    if to_transcribe:
        notes.append("%d file audio o video da trascrivere prima (TXT, DOCX, SRT o VTT)" % len(to_transcribe))
    if unknown:
        notes.append("%d file fuori dalle cartelle note: classificali tu nell'elenco" % len(unknown))
    if skipped:
        notes.append("%d file in un formato non supportato (per esempio .ppt, .key, .odp): esportali in PDF"
                     % len(skipped))
    if not any(found.values()):
        notes.append("nessuna sottocartella riconosciuta: usa slide/, trascrizioni/, esami/, altro/")
    return lines, notes


def course_rel(path, root):
    """Percorso di una fonte relativo alla cartella del corso, in minuscolo ("modulo1/slide/01.pdf"),
    o None se il corso non è noto o il file sta fuori. È ciò che identifica una fonte quando il corso
    viene spostato o riallegato in una chat nuova, dove cambia solo la parte prima della cartella."""
    if root is None:
        return None
    try:
        rel = Path(os.path.abspath(str(path))).relative_to(os.path.abspath(str(root)))
    except ValueError:
        return None
    return rel.as_posix().lower()


def common_tail(a, b):
    """Quanti componenti finali hanno in comune due percorsi (senza distinguere maiuscole)."""
    pa = [s.lower() for s in Path(a).parts if s != "."]
    pb = [s.lower() for s in Path(b).parts if s != "."]
    n = 0
    while n < min(len(pa), len(pb)) and pa[-1 - n] == pb[-1 - n]:
        n += 1
    return n


def same_place(a, b):
    """Stesso percorso visto dalla cartella da cui si lancia lo script ("programma.pdf" e "./programma.pdf")."""
    norm = lambda p: os.path.normcase(os.path.abspath(str(p))).lower()
    return norm(a) == norm(b)


def match_score(entry, path, rel):
    """Quanto il file path (rel: il suo percorso nel corso, o None) somiglia alla fonte entry
    dell'indice: 0 se è un altro file, più alto se corrisponde meglio.

    Con il percorso nel corso da tutte e due le parti, uno deve finire con l'altro: modulo1/slide/01.pdf
    e modulo2/slide/01.pdf sono due fonti, slide/01.pdf e modulo1/slide/01.pdf (corso riorganizzato
    in moduli) possono essere la stessa. Altrimenti basta lo stesso percorso visto da qui, oppure
    cartella e nome uguali come nelle versioni precedenti dello script: più componenti finali uguali,
    migliore la corrispondenza."""
    old = entry.get("rel")
    if old and rel:
        n = common_tail(old, rel)
        if n < min(len(old.split("/")), len(rel.split("/"))):
            return 0
        return 2000 if old == rel else 1000 + n
    if same_place(entry["file"], path):
        return 1500
    if old:  # la fonte ha il percorso nel corso, path no: path deve finire con quel percorso
        n = common_tail(old, path)
        return 1000 + n if n >= len(old.split("/")) else 0
    n = common_tail(entry["file"], rel or path)
    return n if n >= 2 else 0


@functools.lru_cache(maxsize=None)
def file_sha1(path):
    try:
        return hashlib.sha1(Path(path).read_bytes()).hexdigest()
    except OSError:
        return None


def text_lines(text):
    return [" ".join(l.split()) for l in text.split("\n") if l.strip()]


def saved_units(text, sid):
    """[(etichetta, righe)] di un file di _fonti/, senza gli avvisi dello script."""
    out = []
    for m in re.finditer(r"(?ms)^## \[%s, (.+?)\]\n(.*?)(?=^## \[|\Z)" % re.escape(sid), text):
        out.append((m.group(1), [l for l in text_lines(m.group(2)) if not l.startswith("⚠")
                                 and l != "(nessun testo estratto)"]))
    return out


def in_order(small, big):
    """Le righe di small compaiono tutte in big, nello stesso ordine (big può averne altre in mezzo)."""
    it = iter(big)
    return all(any(line == other for other in it) for line in small)


@functools.lru_cache(maxsize=None)
def fresh_units(prefix, path):
    """Unità estratte da un file come se fosse una fonte di tipo prefix (S, T, E, X), o None."""
    try:
        return [(label, text_lines(text or "")) for label, text, _ in extract(prefix + "0", Path(path))[0]]
    except Exception:  # file illeggibile o formato non supportato: non si può dire
        return None


@functools.lru_cache(maxsize=None)
def same_extraction(fonti, sid, path):
    """Per una fonte estratta da una versione dello script che non salvava il contenuto (sha1): il
    file path dà lo stesso testo di _fonti/<ID>.md, unità per unità? Le letture visive aggiunte
    dopo, anche su più righe, stanno in mezzo al testo estratto e non contano."""
    try:
        saved = saved_units((Path(fonti) / (sid + ".md")).read_text(encoding="utf-8", errors="replace"), sid)
    except OSError:
        return False
    fresh = fresh_units(sid[0], str(path))
    # una foto o una scansione non ha testo: due immagini diverse "coinciderebbero" sempre
    if not saved or fresh is None or len(re.sub(r"\s", "", "".join(l for _, ls in fresh for l in ls))) < LOW_TEXT:
        return False
    return len(saved) == len(fresh) and all(a == c and in_order(b, d) for (c, d), (a, b) in zip(saved, fresh))


def by_content(pairs, fonti=None):
    """Fra terne (ID, fonte dell'indice, file) a pari merito, la sola con lo stesso contenuto, o None.
    Serve quando il nome non basta: slide/01.pdf spostato in modulo1/slide/ accanto a modulo2/slide/01.pdf.
    Per le fonti senza sha1 (indici delle versioni precedenti) si confronta il testo estratto."""
    def same(k, e, p):
        if e.get("sha1"):
            return e["sha1"] == file_sha1(str(p))
        return bool(fonti) and same_extraction(str(fonti), k, str(p))
    hits = [(k, e, p) for k, e, p in pairs if same(k, e, p)]
    if len(hits) > 1 and len({k for k, _, _ in hits}) == 1 and len({file_sha1(str(p)) for _, _, p in hits}) == 1:
        return min(hits, key=lambda h: natural_key(h[2]))  # copie identiche: qualunque tiene valide le citazioni
    return hits[0] if len(hits) == 1 else None


MAX_COMPARE = 200  # confronti di testo al massimo per ritrovare i file rinominati


def assign_known(paths, index, root, ambiguous=None, fonti=None, kinds=None):
    """Per i file di un comando, l'ID con cui sono già stati estratti: {percorso: ID}. Ogni ID va al
    solo file che gli corrisponde meglio; a pari merito decide il contenuto, se no non va a nessuno
    e il file prende un ID nuovo. Un file che il percorso non riconosce (cartella del modulo
    rinominata, file rinominato) tiene l'ID di una fonte rimasta senza file con lo stesso contenuto.
    In ambiguous, se c'è, finiscono gli ID che nessuno tiene perché più file gli somigliano allo stesso modo.
    kinds, se c'è, dà la lettera del tipo previsto per ogni file (S, T, E, X): un file rinominato ritrovato dal
    testo tiene l'ID solo se è dello stesso tipo."""
    sources = {k: v for k, v in index.items() if not v.get("diviso")}
    claims = {}  # ID già estratto -> file che gli corrispondono meglio che a ogni altro ID, con il punteggio
    for path in paths:
        rel = course_rel(path, root)
        scores = {k: match_score(v, path, rel) for k, v in sources.items()}
        best = max(scores.values(), default=0)
        ids = [k for k, s in scores.items() if s == best]
        if best and len(ids) > 1:
            pick = by_content([(k, sources[k], path) for k in ids], fonti)
            ids = [pick[0]] if pick else []
        if best and len(ids) == 1:
            claims.setdefault(ids[0], []).append((best, path))
    out = {}
    for known, cands in sorted(claims.items()):
        top = max(s for s, _ in cands)
        winners = [p for s, p in cands if s == top]
        if len(winners) > 1:
            pick = by_content([(known, sources[known], p) for p in winners], fonti)
            if not pick and ambiguous is not None:
                ambiguous[known] = winners
            winners = [pick[2]] if pick else []
        if len(winners) == 1:
            out[winners[0]] = known
    # fonti rimaste senza file (cartella o file rinominati): non una copia di un file che c'è ancora
    free = {k: v for k, v in sources.items() if k not in out.values() and v.get("sha1") and not os.path.exists(v["file"])}
    by_sha = {}
    for path in paths:
        if path not in out and file_sha1(str(path)):
            by_sha.setdefault(file_sha1(str(path)), []).append(path)
    for sha, cands in by_sha.items():
        same = [k for k, v in free.items() if v["sha1"] == sha]
        if len(cands) == 1 and len(same) == 1:
            out[cands[0]] = same[0]
            if ambiguous is not None:
                ambiguous.pop(same[0], None)
    if fonti:  # fonti di una versione precedente (senza sha1) il cui file non c'è più: file rinominato?
        lost = [k for k, v in sources.items() if k not in out.values() and not v.get("sha1")
                and not os.path.exists(v["file"])]
        pairs = [(k, p) for k in lost for p in paths if p not in out
                 and Path(p).suffix.lower() == Path(sources[k]["file"]).suffix.lower()
                 and (kinds is None or kinds.get(p, k[0]) == k[0])]
        if len(pairs) <= MAX_COMPARE:  # ogni confronto estrae di nuovo il file
            hits = [(k, p) for k, p in pairs if same_extraction(str(fonti), k, str(p))]
            for k, p in hits:
                if sum(1 for kk, _ in hits if kk == k) == 1 and sum(1 for _, pp in hits if pp == p) == 1:
                    out[p] = k
    return out


def keep_known_ids(lines, index, root, fonti=None):
    """Rilanciando --corso, un file già estratto tiene il suo ID (le citazioni già scritte restano
    valide) e un file nuovo prende un ID libero, invece di spostare la numerazione degli altri.
    Restituisce (righe, ID cambiati, avvisi)."""
    taken = set(index)
    planned = [l.partition("=") for l in lines]
    ambiguous = {}
    paths = [(sid, path) for sid, sep, path in planned if sep and not sid.startswith("#") and sid != "T"]
    keep = assign_known([p for _, p in paths], index, root, ambiguous, fonti, {p: s[0] for s, p in paths})
    doubts = ["%s (%s) corrisponde allo stesso modo a %s: nessuno lo tiene e prendono ID nuovi. Se uno è "
              "quel file, dagli %s nell'elenco e rilancia con --lista" % (k, Path(index[k]["file"]).name,
                                                                          " e ".join(ps), k)
              for k, ps in sorted(ambiguous.items())]
    taken |= set(keep.values())
    out, changed = [], []
    for line, (sid, sep, path) in zip(lines, planned):
        if line.startswith("#") or not sep or sid == "T":
            out.append(line)
            continue
        new = keep.get(path)
        if new is None and sid in taken:
            if re.fullmatch(r"[STX]\d+", sid):
                same = [int(t[1:]) for t in taken if re.fullmatch(sid[0] + r"\d+", t)]
                new = "%s%02d" % (sid[0], max(same) + 1)
            else:
                new = next(sid + "-%d" % n for n in range(2, 100) if sid + "-%d" % n not in taken)
        new = new or sid
        if new != sid:
            changed.append("%s → %s (%s)" % (sid, new, Path(path).name))
        taken.add(new)
        out.append("%s=%s" % (new, path))
    return out, changed, doubts

# ---------------------------------------------------------------- PDF


def pymupdf():
    """Il modulo PyMuPDF, o None. Dalla versione 1.24.3 si importa come pymupdf: il vecchio nome
    fitz è deprecato, e su PyPI esiste anche un pacchetto "fitz" che non c'entra."""
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


def pdf_pages(path):
    errors = []
    if shutil.which("pdftotext"):
        proc = subprocess.run(["pdftotext", "-enc", "UTF-8", str(path), "-"],
                              capture_output=True, encoding="utf-8", errors="replace")
        if proc.returncode == 0:
            out = proc.stdout
            pages = out.split("\f")
            if out.endswith("\f"):
                pages.pop()
            return pages
        errors.append("pdftotext: " + proc.stderr.strip())
    fitz = pymupdf()
    if fitz:
        try:
            with fitz.open(str(path)) as doc:
                return [p.get_text() for p in doc]
        except Exception as e:
            errors.append("PyMuPDF: %s" % e)
    for mod in ("pypdf", "PyPDF2"):
        try:
            reader = __import__(mod).PdfReader(str(path))
            return [(p.extract_text() or "") for p in reader.pages]
        except ImportError:
            continue
        except Exception as e:  # PDF corrotto o cifrato: prova il prossimo estrattore
            errors.append("%s: %s" % (mod, e))
    try:
        import pdfplumber
        with pdfplumber.open(str(path)) as pdf:
            return [(p.extract_text() or "") for p in pdf.pages]
    except ImportError:
        pass
    except Exception as e:
        errors.append("pdfplumber: %s" % e)
    detail = "; ".join(errors) if errors else "nessun estrattore PDF disponibile"
    raise RuntimeError(detail + ". Installa pypdf (pip install pypdf) o poppler (pdftotext); "
                       "se non puoi installare nulla, leggi il PDF direttamente e numera tu le pagine.")

# ---------------------------------------------------------------- PPTX

NS = {
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}
A = "{%s}" % NS["a"]
P = "{%s}" % NS["p"]
REL = "{http://schemas.openxmlformats.org/package/2006/relationships}Relationship"
NOTES_SKIP = ("sldNum", "sldImg", "hdr", "ftr", "dt")


def read_rels(z, rels_path):
    if rels_path not in z.namelist():
        return {}
    root = ET.fromstring(z.read(rels_path))
    return {r.get("Id"): (r.get("Type", ""), r.get("Target", "")) for r in root.iter(REL)}


def resolve(base_dir, target):
    if target.startswith("/"):
        return target.lstrip("/")
    return posixpath.normpath(posixpath.join(base_dir, target))


def para_text(para):
    parts = []
    for el in para.iter():
        if el.tag == A + "t":
            parts.append(el.text or "")
        elif el.tag == A + "br":
            parts.append(" ")
    return re.sub(r"[ \t]+", " ", "".join(parts)).strip()


def shape_lines(xml_bytes, skip_ph=(), bullets=True):
    root = ET.fromstring(xml_bytes)
    lines = []
    for el in root.iter():
        if el.tag == P + "sp":
            ph = el.find("p:nvSpPr/p:nvPr/p:ph", NS)
            ph_type = ph.get("type") if ph is not None else None
            if ph_type in skip_ph:
                continue
            is_title = ph_type in ("title", "ctrTitle")
            for para in el.iter(A + "p"):
                text = para_text(para)
                if not text:
                    continue
                if is_title:
                    lines.append("**%s**" % text)
                elif bullets:
                    ppr = para.find(A + "pPr")
                    lvl = int(ppr.get("lvl", "0")) if ppr is not None else 0
                    lines.append("  " * lvl + "- " + text)
                else:
                    lines.append(text)
        elif el.tag == P + "graphicFrame":
            for tr in el.iter(A + "tr"):
                cells = [" ".join(para_text(p) for p in tc.iter(A + "p")).strip()
                         for tc in tr.iter(A + "tc")]
                if any(cells):
                    lines.append("| " + " | ".join(cells) + " |")
    has_pic = root.find(".//" + P + "pic") is not None
    hidden = root.get("show") == "0"
    return lines, has_pic, hidden


def pptx_slides(path):
    """Restituisce una lista di (testo, note) nell'ordine della presentazione."""
    slides = []
    with zipfile.ZipFile(path) as z:
        pres = ET.fromstring(z.read("ppt/presentation.xml"))
        rels = read_rels(z, "ppt/_rels/presentation.xml.rels")
        for sld in pres.findall("p:sldIdLst/p:sldId", NS):
            rid = sld.get("{%s}id" % NS["r"])
            target = resolve("ppt", rels[rid][1])
            lines, has_pic, hidden = shape_lines(z.read(target), ("sldNum", "ftr", "dt", "hdr"))
            notes = []
            sdir, sname = posixpath.split(target)
            for typ, tgt in read_rels(z, posixpath.join(sdir, "_rels", sname + ".rels")).values():
                if typ.endswith("/notesSlide"):
                    notes, _, _ = shape_lines(z.read(resolve(sdir, tgt)), NOTES_SKIP, bullets=False)
            flags = []
            if hidden:
                flags.append("slide nascosta nel file originale")
            if has_pic:
                flags.append("contiene immagini")
            body = "\n".join(lines)
            if notes:
                body += "\n\n**Note del relatore:** " + " ".join(notes)
            slides.append((body, flags, len(re.sub(r"\s", "", "\n".join(lines)))))
    return slides

# ---------------------------------------------------------------- DOCX / testo

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def docx_text(path):
    with zipfile.ZipFile(path) as z:
        root = ET.fromstring(z.read("word/document.xml"))
    paras = []
    for p in root.iter(W + "p"):
        parts = []
        for el in p.iter():
            if el.tag == W + "t":
                parts.append(el.text or "")
            elif el.tag == W + "tab":
                parts.append("\t")
            elif el.tag in (W + "br", W + "cr"):
                parts.append("\n")
        paras.append("".join(parts))
    return "\n".join(paras)


def read_text(path):
    """UTF-16 (con BOM), UTF-8 o, se il testo non è UTF-8, cp1252. Pochi byte errati in un file
    UTF-8 non devono far rileggere tutto in cp1252, che storpierebbe ogni lettera accentata."""
    data = path.read_bytes()
    if data[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return data.decode("utf-16")
    text = data.decode("utf-8-sig", errors="replace")
    if text.count("\ufffd") <= max(3, len(text) // 1000):
        return text
    return data.decode("cp1252", errors="replace")


def split_long(text, target=PARA_TARGET, maxlen=PARA_MAX):
    """Spezza un blocco troppo lungo su confini di frase (o di parola, se manca la punteggiatura)."""
    if len(text) <= maxlen:
        return [text]
    sentences = re.split(r"(?<=[.!?…])\s+", text)
    pieces = []
    for s in sentences:
        while len(s) > maxlen:
            cut = s.rfind(" ", 0, target)
            cut = cut if cut > 0 else target
            pieces.append(s[:cut].strip())
            s = s[cut:].strip()
        pieces.append(s)
    out, cur = [], ""
    for s in pieces:
        if cur and len(cur) + len(s) + 1 > target:
            out.append(cur)
            cur = s
        else:
            cur = (cur + " " + s).strip()
    if cur:
        out.append(cur)
    return out


def chunk_paragraphs(text):
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    if re.search(r"\n\s*\n", text):
        blocks = re.split(r"\n\s*\n", text)
    else:
        blocks = text.split("\n")
    blocks = [re.sub(r"\s+", " ", b).strip() for b in blocks]
    out, cur = [], ""
    for b in blocks:
        if not b:
            continue
        for piece in split_long(b):
            if cur and len(cur) + len(piece) + 1 > PARA_TARGET:
                out.append(cur)
                cur = piece
            else:
                cur = (cur + " " + piece).strip()
    if cur:
        out.append(cur)
    return out

def chunk_markdown(text):
    """Paragrafi di un file Markdown: ogni titolo apre un nuovo paragrafo, le righe restano
    (tabelle ed elenchi si leggono ancora), i blocchi brevi si uniscono fino a ~PARA_TARGET."""
    blocks = [b.strip("\n") for b in re.split(r"\n\s*\n", text.replace("\r\n", "\n")) if b.strip()]
    out, cur = [], ""
    for b in blocks:
        starts_section = b.lstrip().startswith("#")
        if cur and (starts_section or len(cur) + len(b) > PARA_TARGET):
            out.append(cur)
            cur = b
        else:
            cur = (cur + "\n\n" + b) if cur else b
    if cur:
        out.append(cur)
    return out

# ---------------------------------------------------------------- timestamp

TS = r"\d{1,2}:\d{1,2}(?::\d{1,2})?(?:[.,]\d{1,3})?"
# "Nome Cognome", "Speaker 1", "Prof. X": parole con iniziale maiuscola o numeri, al massimo 4
SPEAKER = r"(?:[A-ZÀ-Ý][\w.'’-]*)(?:\s+(?:[A-ZÀ-Ý][\w.'’-]*|\d+)){0,3}"
# "[00:42:10] testo", "00:42 - testo", "[00:00.000 --> 00:05.000] testo" (Whisper)
LINE_TS = re.compile(r"^\s*[\[(]?(?P<ts>" + TS + r")(?:\s*(?:-->|-|–)\s*" + TS
                     + r")?[\])]?\s*[-–—:|]?\s*(?P<rest>.*)$")
# "Nome Cognome  0:42" su una riga, testo nelle righe seguenti, oppure "Nome Cognome 0:42 testo"
SPEAKER_TS = re.compile(r"^\s*(?P<spk>" + SPEAKER + r")\s+[\[(]?(?P<ts>" + TS
                        + r")[\])]?\s*(?:[-–—:|]\s*)?(?P<rest>.*)$")
BLOCK_SECONDS = 60     # un blocco con timestamp copre al massimo circa un minuto


def ts_seconds(ts):
    ts = re.split(r"[.,]", ts)[0]
    parts = [int(x) for x in ts.split(":")]
    if len(parts) == 2:
        return parts[0] * 60 + parts[1]
    return parts[0] * 3600 + parts[1] * 60 + parts[2]


def fmt_ts(sec):
    return "%02d:%02d:%02d" % (sec // 3600, sec % 3600 // 60, sec % 60)


def parse_cues(text):
    """SRT/VTT: lista di (secondi, testo)."""
    segs = []
    for block in re.split(r"\n\s*\n", text.replace("\r\n", "\n")):
        lines = [l for l in block.strip().split("\n") if l.strip()]
        for i, line in enumerate(lines):
            if "-->" in line:
                m = re.match(r"\s*(" + TS + r")", line)
                body = " ".join(lines[i + 1:])
                body = re.sub(r"<v\s+([^>]+)>", r"\1: ", body)
                body = re.sub(r"<[^>]+>", "", body).strip()
                if m and body:
                    segs.append((ts_seconds(m.group(1)), body))
                break
    return segs


def parse_inline_timestamps(text):
    """Testo con timestamp a inizio riga o righe 'Nome  00:42'. None se non è un testo con timestamp."""
    lines = text.replace("\r\n", "\n").split("\n")
    line_hits = [LINE_TS.match(l) for l in lines]
    spk_hits = [SPEAKER_TS.match(l) for l in lines]
    if sum(map(bool, line_hits)) >= sum(map(bool, spk_hits)):
        hits = line_hits
    else:
        # un vero speaker ricorre o sta da solo sulla riga col suo timestamp;
        # "Alle 10:30 facciamo pausa" non fa nessuna delle due cose e resta testo normale
        counts = {}
        for m in spk_hits:
            if m:
                counts[m.group("spk")] = counts.get(m.group("spk"), 0) + 1
        hits = [m if m and (counts[m.group("spk")] >= 2 or not m.group("rest").strip()) else None
                for m in spk_hits]
    if sum(map(bool, hits)) < 3:
        return None

    segs, cur_ts, cur, preamble = [], None, [], []
    for line, m in zip(lines, hits):
        if m:
            if cur_ts is not None:
                segs.append((cur_ts, " ".join(cur).strip()))
            cur_ts = ts_seconds(m.group("ts"))
            cur = [m.group("spk") + ":"] if "spk" in m.groupdict() else []
            if m.group("rest").strip():
                cur.append(m.group("rest").strip())
        elif line.strip():
            (cur if cur_ts is not None else preamble).append(line.strip())
    if cur_ts is not None:
        segs.append((cur_ts, " ".join(cur).strip()))
    segs = [s for s in segs if not re.fullmatch(r"[^:]*:", s[1])]  # solo il nome, senza testo
    if not segs:
        return None
    decreasing = sum(1 for a, b in zip(segs, segs[1:]) if b[0] < a[0])
    if decreasing > 0.2 * len(segs):
        return None
    if preamble and segs:
        segs[0] = (segs[0][0], " ".join(preamble) + " " + segs[0][1])
    return [s for s in segs if s[1]]


def group_segments(segs):
    """Unisce segmenti brevi in blocchi (circa BLOCK_TARGET caratteri o BLOCK_SECONDS secondi),
    etichettati col primo timestamp, così le citazioni restano precise ma non troppo frammentate."""
    blocks = []
    for sec, body in segs:
        if blocks and ((len(blocks[-1][1]) < BLOCK_TARGET and 0 <= sec - blocks[-1][0] < BLOCK_SECONDS)
                       or fmt_ts(sec) == fmt_ts(blocks[-1][0])):
            blocks[-1] = (blocks[-1][0], blocks[-1][1] + " " + body)
        else:
            blocks.append((sec, body))
    return blocks

# ---------------------------------------------------------------- estrazione per fonte


def nonspace(s):
    return len(re.sub(r"\s", "", s))


def looks_like_layout(text):
    """Diagrammi, alberi e formule a più livelli escono dall'estrazione come tante righe di
    uno o due simboli ("A", "→", "x1", "+"): il testo c'è, ma la struttura si è persa.
    I numeri da soli (gli indici delle slide Beamer) non contano."""
    lines = [l.strip() for l in text.split("\n") if l.strip() and not l.strip().isdigit()]
    if len(lines) < 8:
        return False
    short = sum(1 for l in lines if len(l) <= 4)
    return short >= 0.4 * len(lines)


PAGE_COUNTER = re.compile(r"^\d+\s*/\s*\d+$")  # "12 / 73" dei piè di pagina Beamer


def pdf_image_pages(path, n_pages):
    """Pagine con immagini di contenuto, che l'estrazione del testo non vede.

    Esclude le immagini ripetute su molte pagine (loghi, sfondi), quelle piccole (icone)
    e le strisce molto allungate (sfondi di riquadri). Usa pdfimages (poppler) o PyMuPDF:
    senza nessuno dei due, restituisce un insieme vuoto."""
    images = []  # (pagina, larghezza, altezza)
    if shutil.which("pdfimages"):
        proc = subprocess.run(["pdfimages", "-list", str(path)], capture_output=True, text=True)
        for line in proc.stdout.splitlines()[2:]:
            f = line.split()
            if len(f) > 11 and f[2] == "image" and f[0].isdigit() and f[3].isdigit() and f[4].isdigit():
                images.append((int(f[0]), int(f[3]), int(f[4]), f[10]))  # f[10]: numero dell'oggetto
    else:
        try:
            with pymupdf().open(str(path)) as doc:
                for page in doc:
                    # get_image_info vede anche le immagini inline, che get_images non elenca
                    images += [(page.number + 1, img["width"], img["height"], img["digest"])
                               for img in page.get_image_info(hashes=True)]
        except Exception:  # PyMuPDF assente o PDF illeggibile: nessuna segnalazione di immagini
            return set()
    rows = [(page, sig) for page, w, h, sig in images
            if w >= 120 and h >= 90 and max(w / h, h / w) < 4]
    counts = {}
    for _, sig in rows:
        counts[sig] = counts.get(sig, 0) + 1
    return {page for page, sig in rows if counts[sig] < max(2, 0.3 * n_pages)}


def strip_repeated_lines(pages):
    """Toglie intestazioni e piè di pagina ripetuti (autore, corso, anno, numero di pagina).

    Soglia 80%: i nomi di sezione Beamer possono stare su più di metà delle pagine e vanno tenuti.

    Sono rumore: sprecano contesto e, soprattutto, fanno sembrare piena di testo una
    slide che contiene solo un'immagine, che così non verrebbe segnalata."""
    n = len(pages)
    repeated = set()
    if n >= 6:
        counts = {}
        for text in pages:
            for line in {l.strip() for l in text.split("\n") if l.strip()}:
                counts[line] = counts.get(line, 0) + 1
        repeated = {l for l, c in counts.items() if c >= max(3, 0.8 * n) and len(l) <= 100}
    # "12 / 73" è un contatore solo se il denominatore è lo stesso su molte pagine
    dens = [m.group(1) for t in pages for m in re.finditer(r"(?m)^\s*\d+\s*/\s*(\d+)\s*$", t)]
    counter_dens = {d for d in set(dens) if dens.count(d) >= max(3, 0.5 * n)}
    trailing = sum(1 for i, t in enumerate(pages, 1) if t.strip().split("\n")[-1].strip() == str(i))
    seen = set()
    out = []
    for i, text in enumerate(pages, 1):
        lines = []
        for l in text.split("\n"):
            k = l.strip()
            m = PAGE_COUNTER.match(k)
            if m and k.split("/")[-1].strip() in counter_dens:
                continue
            if k in repeated:
                if k in seen:
                    continue
                seen.add(k)  # la prima occorrenza resta: il titolo di una slide con animazioni non sparisce
            lines.append(l)
        while lines and not lines[-1].strip():
            lines.pop()
        if lines and lines[-1].strip() == str(i) and trailing >= 0.5 * n:  # numeri di pagina sistematici
            lines.pop()
        out.append(re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip())
    return out, sorted(repeated)


def extract(source_id, path):
    """Restituisce (unità, info). Ogni unità è (etichetta, testo, avvisi)."""
    prefix = source_id[0]
    ext = path.suffix.lower()
    info = {"file": path.as_posix(), "kind": KIND_BY_PREFIX[prefix]}
    units = []

    if ext in IMAGE_EXT:
        info["unit"] = "pag"
        units.append(("pag. 1", "", ["file immagine: leggilo visivamente e trascrivi qui il contenuto"]))
        return units, info

    if ext == ".pdf" and prefix != "T":  # le trascrizioni in PDF passano da transcript_units
        label = "slide" if prefix == "S" else "pag."
        info["unit"] = "slide" if prefix == "S" else "pag"
        pages, removed = strip_repeated_lines(pdf_pages(path))
        if removed:
            info["boilerplate"] = removed
        with_images = pdf_image_pages(path, len(pages))
        for i, text in enumerate(pages, 1):
            flags = []
            if nonspace(text) < LOW_TEXT:
                flags.append("poco testo estratto: guarda la pagina visivamente")
            elif i in with_images:
                flags.append("contiene un'immagine: guardala, può contenere testo, una citazione o un diagramma")
            elif looks_like_layout(text):
                flags.append("molte righe cortissime: probabile diagramma, albero o formula impaginata, guardala")
            units.append(("%s %d" % (label, i), text, flags))
        return units, info

    if ext == ".pptx":
        info["unit"] = "slide"
        for i, (text, flags, n) in enumerate(pptx_slides(path), 1):
            if n < LOW_TEXT:
                flags = flags + ["poco testo estratto: guarda la slide visivamente"]
            units.append(("slide %d" % i, text, flags))
        return units, info

    text = document_text(path)
    if prefix == "T":
        return transcript_units(text, ext, info), info
    return paragraph_units(text, ext, info), info


def document_text(path):
    """Testo continuo di un documento (per trascrizioni e paragrafi)."""
    ext = path.suffix.lower()
    if ext == ".docx":
        return docx_text(path)
    if ext in (".txt", ".md", ".srt", ".vtt", ".text", ""):
        return read_text(path)
    if ext == ".pdf":  # solo per le trascrizioni divise in lezioni: le pagine non sono unità utili
        return "\n".join(strip_repeated_lines(pdf_pages(path))[0])
    raise RuntimeError("formato non supportato: %s (converti in PDF, PPTX, DOCX o TXT)" % ext)


def paragraph_units(text, ext, info):
    info["unit"] = "par"
    chunks = chunk_markdown(text) if ext == ".md" else chunk_paragraphs(text)
    return [("par. %d" % i, para, []) for i, para in enumerate(chunks, 1)]


def transcript_units(text, ext, info, restart_hint="se il file contiene più lezioni passalo come T=file; se è "
                     "una lezione registrata in più parti, dividilo in più file (per esempio T03-1=..., T03-2=...)"):
    """Blocchi con timestamp, se il testo ne ha; altrimenti paragrafi numerati."""
    segs = parse_cues(text) if ext in (".srt", ".vtt") else parse_inline_timestamps(text)
    if not segs:
        return paragraph_units(text, ext, info)
    top = 0
    for sec, body in segs:
        if sec < 120 and top >= 600:
            raise RuntimeError("i timestamp ripartono da zero a «%s…»: %s" % (body[:40], restart_hint))
        top = max(top, sec)
    info["unit"] = "ts"
    blocks = group_segments(segs)
    info["seconds"] = [b[0] for b in blocks]
    info["last_seconds"] = segs[-1][0]
    return [(fmt_ts(sec), body, []) for sec, body in blocks]

# ---------------------------------------------------------------- più lezioni in un file

LESSON_WORD = r"(?:lezione|lez\.?|lecture|lesson)"
HEAD_START = r"^\s*(?:#{1,6}\s*)?[*_]*\s*"
# "Lezione 3", "Lezione 3: Titolo", "Lezione 3. Titolo", "LEZIONE N. 3 - 12/03/2026", "Lezione n° 3",
# "## Lecture 3: Search", "**Lez. 3**"; non "Lezione 12/03" (una data) né "Lezione 3.1" (una sottoparte)
LESSON_NUM = re.compile(HEAD_START + LESSON_WORD + r"\s*(?:n(?:r|um)?\s*[.°º]?\s*|#\s*)?(?P<num>\d{1,3})"
                        r"(?![\d/]|[:.,]\d)", re.I)
# "Lezione del 12 marzo", "Lezione 12/03/2026", "Lecture - 3 March"
LESSON_DATE = re.compile(HEAD_START + LESSON_WORD + r"\s*(?:del|of|on|[-–:])?\s*\d{1,2}"
                         r"(?:[/.-]\d{1,2}|\s+[A-Za-zÀ-ÿ]{3,})", re.I)
# un titolo Markdown che nomina la lezione: "# Seconda lezione: alberi di ricerca"
LESSON_MD = re.compile(r"^\s*#{1,6}\s+(?:\S+\s+)?(?:lezione|lecture|lesson)\b", re.I)
MIN_LESSON = 200       # caratteri non-spazio sotto cui una "lezione" è solo un titolo (es. un indice iniziale)


def line_seconds(line):
    m = LINE_TS.match(line)
    if m:
        return ts_seconds(m.group("ts"))
    m = SPEAKER_TS.match(line)
    if m and not m.group("rest").strip():
        return ts_seconds(m.group("ts"))
    return None


def split_lessons(text):
    """Divide un file con più lezioni. Restituisce (parti, criterio); ogni parte è
    (numero o None, titolo, testo). Prima cerca i titoli di lezione, poi i timestamp
    che ripartono da zero; se non trova nulla restituisce una parte sola."""
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    heads = []
    for i, line in enumerate(lines):
        s = line.strip()
        if not s or len(s) > 120:
            continue
        m = LESSON_NUM.match(s)
        if (m or LESSON_DATE.match(s)) and s.endswith((".", "?", "!")) and not LESSON_MD.match(s):
            continue  # una frase che inizia con "Lezione 4 ...", non un titolo
        if m or LESSON_DATE.match(s) or LESSON_MD.match(s):
            heads.append((i, int(m.group("num")) if m else None, re.sub(r"^[#*_\s]+|[*_\s]+$", "", s)))
    how = "titoli di lezione"
    dedup = []
    for h in heads:  # stessa lezione ripetuta (intestazione di pagina, "parte 2"): non è una nuova lezione
        if dedup and h[1] is not None and h[1:] == dedup[-1][1:]:
            continue
        dedup.append(h)
    heads = dedup
    if len(heads) == 1 and heads[0][1] is not None:
        return [(heads[0][1], heads[0][2], text)], "un solo titolo di lezione"
    if len(heads) < 2:
        heads, how, top = [], "timestamp che ripartono da zero", 0
        for i, line in enumerate(lines):
            sec = line_seconds(line)
            if sec is None:
                continue
            if sec < 120 and top >= 600:
                heads.append((i, None, ""))
                top = 0
            top = max(top, sec)
        if heads:
            heads.insert(0, (0, None, ""))
    if len(heads) < 2:
        return [(None, "", text)], "nessuna divisione trovata: una sola lezione"

    if heads[0][0] > 0:  # testo prima del primo titolo: se è corto si unisce alla lezione dopo (sotto)
        heads.insert(0, (0, None, ""))
    parts = []
    starts = [h[0] for h in heads] + [len(lines)]
    for k, (i, num, title) in enumerate(heads):
        parts.append([num, title, "\n".join(lines[i:starts[k + 1]])])
    # titoli senza testo (per esempio un indice delle lezioni in cima): il testo passa alla parte dopo
    merged = []
    for k, p in enumerate(parts):
        if k + 1 < len(parts) and nonspace(p[2]) < MIN_LESSON:
            parts[k + 1][2] = p[2] + "\n" + parts[k + 1][2]
        else:
            merged.append(p)
    return [tuple(p) for p in merged], how


def extract_lessons(path, first=1):
    """Fonti T01, T02, ... da un unico file con più lezioni: lista di (id, unità, info), criterio.
    Il numero viene dal titolo di lezione; senza titoli numerati si conta da `first`, così
    più file passati con T= nello stesso comando non si sovrappongono."""
    ext = path.suffix.lower()
    parts, how = split_lessons(document_text(path))
    nums = [p[0] for p in parts]
    if None not in nums and len(set(nums)) != len(nums):
        # "Lezione 3 (parte 1)", "Lezione 3 (parte 2)": stessa lezione in più parti -> T03-1, T03-2
        ids, seen = [], {}
        for n in nums:
            seen[n] = seen.get(n, 0) + 1
            ids.append("T%02d-%d" % (n, seen[n]) if nums.count(n) > 1 else "T%02d" % n)
        how += " (lezioni in più parti: ID con suffisso -1, -2, ...)"
    else:
        if None in nums:
            if any(n is not None for n in nums):
                how += " (numeri di lezione mancanti: numerate in ordine)"
            nums = list(range(first, first + len(parts)))
        ids = ["T%02d" % n for n in nums]
    out = []
    for sid, (_, title, body) in zip(ids, parts):
        info = {"file": path.as_posix(), "kind": "trascrizione", "diviso": True}
        if title:
            info["lezione"] = title
        hint = ("la lezione «%s» contiene a sua volta più registrazioni: dividi il file a mano" % title
                if title else "dividi il file a mano, un file per lezione")
        out.append((sid, transcript_units(body, ext, info, hint), info))
    return out, how


def write_source(out_dir, source_id, path, units, info):
    low = [u[0] for u in units if any("guard" in f or "immagin" in f for f in u[2])]  # tutti gli avvisi visivi
    lines = ["# %s: %s%s" % (source_id, path.name, " · " + info["lezione"] if info.get("lezione") else ""),
             "<!-- tipo: %s · %d unità · estratto da extract_sources.py -->" % (info["kind"], len(units))]
    if info.get("boilerplate"):
        lines.append("<!-- righe ripetute su ogni pagina, rimosse: %s -->" % " | ".join(info["boilerplate"]))
    if info["unit"] == "slide":
        lines.append("<!-- 'slide N' = N-esima pagina del file, che può differire dal numero nel piè di pagina -->")
    lines.append("")
    if low:
        lines += ["> ⚠ Da guardare visivamente: " + ", ".join(low), ""]
    for label, text, flags in units:
        lines.append("## [%s, %s]" % (source_id, label))
        for f in flags:
            lines.append("⚠ " + f)
        lines.append(text if text else "(nessun testo estratto)")
        lines.append("")
    (out_dir / (source_id + ".md")).write_text("\n".join(lines), encoding="utf-8")
    return low


def describe(info, units):
    n = len(units)
    if info["unit"] == "ts":
        return "%d blocchi con timestamp (%s–%s)" % (n, units[0][0], fmt_ts(info["last_seconds"]))
    names = {"slide": "slide", "pag": "pag.", "par": "paragrafi"}
    return "%d %s" % (n, names[info["unit"]])


def main():
    for stream in (sys.stdout, sys.stderr):  # console Windows (cp1252) con output su pipe
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True, help="cartella di output, es. dispensa/_fonti")
    ap.add_argument("--force", action="store_true", help="sovrascrivi i file già estratti")
    ap.add_argument("--lista", help="file con una coppia ID=FILE per riga (righe vuote e # ignorate): "
                    "evita i problemi di quoting della shell quando i file sono molti")
    ap.add_argument("--corso", help="cartella del corso con le sottocartelle slide/, trascrizioni/, esami/, "
                    "altro/: gli ID vengono assegnati da soli e l'elenco finisce in --elenco")
    ap.add_argument("--elenco", help="dove scrivere l'elenco preparato da --corso (default: elenco.txt "
                    "accanto alla cartella --out)")
    ap.add_argument("sources", nargs="*", metavar="ID=FILE")
    args = ap.parse_args()
    out_dir = Path(args.out)
    index_path = out_dir / "_indice.json"
    index = json.loads(index_path.read_text(encoding="utf-8")) if index_path.exists() else {}
    # una fonte il cui file in _fonti/ è stato cancellato esce dall'indice: è così che si cambia un ID
    gone = sorted(k for k in index if not (out_dir / (k + ".md")).exists())
    for k in gone:
        print("• %s: _fonti/%s.md non c'è più, tolto dall'indice" % (k, k))
        del index[k]
    root = None  # cartella del corso: identifica le fonti con il loro percorso nel corso
    if args.corso:
        if args.lista or args.sources:
            ap.error("--corso prepara da solo l'elenco: non va insieme a --lista o a ID=FILE")
        if not Path(args.corso).is_dir():
            ap.error("--corso: cartella non trovata: %s" % args.corso)
        root = Path(args.corso)
        lines, notes = scan_course(args.corso)
        lines, changed, doubts = keep_known_ids(lines, index, root, out_dir)
        if changed:
            notes.append("ID già usati da fonti estratte prima, nuovi ID: " + "; ".join(changed))
        notes += doubts
        elenco = Path(args.elenco) if args.elenco else Path(args.out).parent / "elenco.txt"
        elenco.parent.mkdir(parents=True, exist_ok=True)
        elenco.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print("Elenco delle fonti scritto in %s:\n" % elenco)
        print("\n".join("  " + l for l in lines[5:] if l))
        for n in notes:
            print("⚠ " + n)
        print()
        args.lista = str(elenco)
    if args.lista:
        text = Path(args.lista).read_text(encoding="utf-8-sig")
        m = re.match(r"# Elenco preparato da extract_sources\.py --corso (.+)", text)
        if root is None and m:  # un elenco scritto da --corso dice nella prima riga qual è il corso
            root = Path(m.group(1).strip())
        for line in text.splitlines():
            if line.strip() and not line.lstrip().startswith("#"):
                args.sources.append(line.strip())
    if not args.sources:
        ap.error("indica almeno una fonte (ID=FILE) o un file --lista")

    out_dir.mkdir(parents=True, exist_ok=True)
    rows, failures = [], 0
    produced, next_t = {}, 1  # ID creati in questo comando; prossimo numero libero per T=
    # file di questo comando già estratti prima, con il loro ID: la stessa regola dell'elenco di --corso
    specs = {str(Path(f.strip()).expanduser()): i.strip()[:1] for i, f in (s.split("=", 1) for s in args.sources if "=" in s)
             if i.strip() != "T"}
    assigned = assign_known(list(specs), index, root, fonti=out_dir, kinds=specs)
    owner = {sid: p for p, sid in assigned.items()}
    seen = {}  # file -> ID in questo comando
    for spec in args.sources:
        if "=" not in spec:
            print("✗ %s: usa il formato ID=FILE" % spec, file=sys.stderr)
            failures += 1
            continue
        source_id, file_arg = (s.strip() for s in spec.split("=", 1))
        path = Path(file_arg).expanduser()
        if not ID_RE.match(source_id) and source_id != "T":
            print("✗ %s: ID non valido (lettera S/T/E/X seguita da una cifra, es. S01, E2023-06; "
                  "solo T per un file con più lezioni)" % source_id, file=sys.stderr)
            failures += 1
            continue
        if not path.is_file():
            print("✗ %s: file non trovato: %s" % (source_id, path), file=sys.stderr)
            failures += 1
            continue
        m = re.match(r"T(\d+)", source_id)
        if m:  # un T= che viene dopo continua la numerazione da qui, anche se questa fonte è già estratta
            next_t = max(next_t, int(m.group(1)) + 1)
        rel = course_rel(path, root)
        prev = produced.get(source_id) or index.get(source_id)
        taken_by = None
        if prev and not match_score(prev, path, rel) and assigned.get(str(path)) != source_id:
            taken_by = prev["file"]
        elif owner.get(source_id, str(path)) != str(path):  # in questo comando l'ID va a un file più somigliante
            taken_by = owner[source_id]
        if source_id != "T" and taken_by and not args.force:
            print("✗ %s: ID già usato per %s; scegli un altro ID per %s" % (source_id, taken_by, path.name),
                  file=sys.stderr)
            failures += 1
            continue
        key = rel or os.path.abspath(str(path)).lower()
        other = assigned.get(str(path)) or seen.get(key)
        if source_id != "T":
            seen.setdefault(key, source_id)
        if source_id != "T" and other and other != source_id:
            # lo stesso file con due ID: le citazioni al vecchio ID resterebbero valide per lo script
            print("✗ %s: %s è già registrato come %s. Per cambiargli ID cancella _fonti/%s.md e rilancia"
                  % (source_id, path.name, other, other), file=sys.stderr)
            failures += 1
            continue
        if source_id != "T" and (out_dir / (source_id + ".md")).exists() and not args.force:
            print("• %s: già estratto, saltato (usa --force per rigenerarlo: perderai le aggiunte manuali)"
                  % source_id)
            entry = index.get(source_id)
            if entry and entry.get("sha1") and entry["sha1"] != file_sha1(str(path)):
                print("⚠ %s: %s è cambiato da quando è stato estratto. Se è una versione aggiornata rigeneralo "
                      "con --force (perderai le aggiunte manuali); se è un'altra fonte dagli un ID nuovo"
                      % (source_id, path.name))
            elif entry:  # il corso può essere stato spostato: l'indice segue il file dov'è ora
                entry["file"] = path.as_posix()
                if rel:
                    entry["rel"] = rel
                if file_sha1(str(path)):
                    entry["sha1"] = file_sha1(str(path))
            continue
        try:
            if source_id == "T":
                # senza titoli di lezione numerati, un file come "lezione05.txt" resta T05
                first = next_t if next_t > 1 else (file_number(path) or 1)
                found, how = extract_lessons(path, first)
                next_t = max([next_t] + [int(re.match(r"T(\d+)", sid).group(1)) + 1 for sid, _, _ in found])
                print("• %s: %d %s (%s)" % (path.name, len(found), "lezione" if len(found) == 1 else "lezioni", how))
            else:
                found = [(source_id,) + extract(source_id, path)]
        except Exception as e:
            print("✗ %s (%s): %s" % (source_id, path.name, e), file=sys.stderr)
            failures += 1
            continue
        for sid, units, info in found:
            prev = produced.get(sid) or index.get(sid)
            if source_id == "T" and prev and not match_score(prev, path, rel) and not args.force:
                print("✗ %s: ID già usato per %s; la lezione %s di %s non è stata estratta (dividi il file "
                      "e dai ID espliciti, per esempio T%02d=...)"
                      % (sid, prev["file"], info.get("lezione") or sid, path.name, next_t), file=sys.stderr)
                failures += 1
                continue
            if (out_dir / (sid + ".md")).exists() and not args.force:
                print("• %s: già estratto, saltato (usa --force per rigenerarlo: perderai le aggiunte manuali)"
                      % sid)
                continue
            if not units:
                print("✗ %s (%s): nessun contenuto estratto" % (sid, path.name), file=sys.stderr)
                failures += 1
                continue
            low = write_source(out_dir, sid, path, units, info)
            if rel:
                info["rel"] = rel
            if file_sha1(str(path)):
                info["sha1"] = file_sha1(str(path))
            produced[sid] = info
            info["labels"] = [u[0] for u in units]
            info["low_text"] = low
            index[sid] = info
            note = "«%s»" % info["lezione"] if info.get("lezione") else ""
            if low:
                shown = ", ".join(l.split()[-1] for l in low[:15]) + (" …" if len(low) > 15 else "")
                note = "%d da guardare visivamente: %s" % (len(low), shown)
            elif info["kind"] == "trascrizione" and info["unit"] == "par":
                note = (note + " · " if note else "") + "nessun timestamp: paragrafi numerati"
            rows.append("| %s | %s | %s | %s | %s |" % (sid, path, info["kind"], describe(info, units), note))

    index_path.write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")
    if rows:
        print("\n| ID | File | Tipo | Unità | Note |\n|---|---|---|---|---|")
        print("\n".join(rows))
    print("\nIndice: %s (%d fonti in totale)" % (index_path, len(index)))
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
