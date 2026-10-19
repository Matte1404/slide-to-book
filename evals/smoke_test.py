#!/usr/bin/env python3
"""Controllo rapido della skill slide-to-book, usato anche dalla GitHub Action.

Uso:
    pip install pyyaml pymupdf
    python3 evals/smoke_test.py

Verifica che il frontmatter di SKILL.md sia valido per claude.ai (YAML, nome, lunghezza
della descrizione), che i file citati da SKILL.md esistano, e fa girare gli script sui
corsi di prova di make_fixtures.py: estrazione con divisione delle trascrizioni,
controllo delle citazioni (uno che passa e uno che deve fallire), unione dei capitoli e
cartella del corso con --corso.
"""

import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / "slide-to-book"
SCRIPTS = SKILL / "scripts"
ALLOWED_KEYS = {"name", "description", "license", "allowed-tools", "metadata", "compatibility"}
failures = []


def check(cond, msg):
    print(("  ✓ " if cond else "  ✗ ") + msg)
    if not cond:
        failures.append(msg)


def run(*args, expect=0):
    proc = subprocess.run([sys.executable, *map(str, args)], capture_output=True, text=True)
    if proc.returncode != expect:
        print(proc.stdout[-2000:], proc.stderr[-2000:], sep="\n")
    return proc


def frontmatter():
    print("SKILL.md")
    text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    check(bool(m), "frontmatter presente")
    try:
        meta = yaml.safe_load(m.group(1))
    except yaml.YAMLError as e:  # per esempio un ':' seguito da spazio dentro la descrizione
        check(False, "frontmatter YAML valido (%s)" % str(e).splitlines()[0])
        return
    check(isinstance(meta, dict), "frontmatter YAML valido")
    check(set(meta) <= ALLOWED_KEYS, "solo campi ammessi: %s" % ", ".join(sorted(meta)))
    check(meta.get("name") == SKILL.name, "name uguale al nome della cartella")
    check(re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", meta.get("name", "")) is not None, "name in kebab-case")
    desc = meta.get("description", "")
    check(0 < len(desc) <= 1024, "descrizione di %d caratteri (max 1024)" % len(desc))
    check("<" not in desc and ">" not in desc, "descrizione senza parentesi angolari")
    check(text.count("\n") < 500, "SKILL.md sotto le 500 righe (%d)" % text.count("\n"))
    for ref in sorted(set(re.findall(r"`((?:references|scripts)/[\w.-]+)`", text))):
        check((SKILL / ref).is_file(), "esiste %s" % ref)


def scripts(tmp):
    print("Script sul corso di prova")
    corso, fonti = tmp / "corso", tmp / "_fonti"
    run(ROOT / "evals" / "make_fixtures.py", corso)
    proc = run(SCRIPTS / "extract_sources.py", "--out", fonti,
               "S01=%s" % (corso / "lez01_sistemi.pdf"), "S02=%s" % (corso / "lez02_primo_ordine.pdf"),
               "T=%s" % (corso / "trascrizioni_lezioni.docx"),
               "E2025-06=%s" % (corso / "esame_2025-06-16.pdf"), "E2025-09=%s" % (corso / "esame_2025-09-10.pdf"))
    check(proc.returncode == 0, "extract_sources.py termina senza errori")
    check((fonti / "T01.md").is_file() and (fonti / "T02.md").is_file(), "trascrizioni divise in T01 e T02")
    s01 = (fonti / "S01.md").read_text(encoding="utf-8")
    check(s01.count("## [S01, slide") == 6, "S01 ha 6 slide")
    check("Da guardare visivamente: slide 5" in s01, "slide-diagramma segnalata per la lettura visiva")

    book = tmp / "capitoli"
    book.mkdir()
    (book / "01-sistemi.md").write_text(
        "# Capitolo 1: Sistemi\n\nDefinizione [S01, slide 1-6]. Primo ordine [S02, slide 1-6].\n\n"
        "Il docente ha detto che la sovrapposizione esce sempre [T01, 00:30:00].\n\n"
        "Esercizi [E2025-06, es. 1]; [E2025-09, es. 1].\n", encoding="utf-8")
    proc = run(SCRIPTS / "check_coverage.py", "--fonti", fonti, "--libro", book, "--copertura", tmp / "copertura.md")
    check(proc.returncode == 0, "check_coverage.py accetta citazioni valide e copertura completa")
    (book / "02-errore.md").write_text("# Capitolo 2\n\nSlide inesistente [S02, slide 9].\n", encoding="utf-8")
    proc = run(SCRIPTS / "check_coverage.py", "--fonti", fonti, "--libro", book, expect=1)
    check(proc.returncode == 1 and "S02 ha solo 6" in proc.stdout, "check_coverage.py rifiuta una slide inesistente")

    proc = run(SCRIPTS / "merge_book.py", "--capitoli", book, "--out", tmp / "dispensa.md", "--titolo", "Prova")
    check(proc.returncode == 0 and (tmp / "dispensa.md").is_file(), "merge_book.py unisce i capitoli")
    proc = run(SCRIPTS / "visual.py", "todo", "--fonti", fonti)
    check(proc.returncode == 0 and "S01: 5" in proc.stdout, "visual.py todo elenca le slide da guardare")


def folders(tmp):
    print("Cartella del corso (--corso)")
    corso, out = tmp / "corso", tmp / "dispensa" / "_fonti"
    run(ROOT / "evals" / "make_fixtures.py", "--cartelle", corso)
    proc = run(SCRIPTS / "extract_sources.py", "--out", out, "--corso", corso)
    check(proc.returncode == 0, "extract_sources.py --corso termina senza errori")
    elenco = (tmp / "dispensa" / "elenco.txt").read_text(encoding="utf-8")
    ids = {l.split("=", 1)[0] for l in elenco.splitlines() if l and not l.startswith("#")}
    check(ids == {"S01", "S02", "T01", "T02", "E2025-06", "E2025-06-sol", "E2025-09", "X01"},
          "ID assegnati dai nomi: %s" % ", ".join(sorted(ids)))
    check("da trascrivere prima" in elenco and "lezione03.m4a" in elenco, "la registrazione audio è segnalata")
    check("da classificare" in elenco and "note_varie.txt" in elenco, "il file fuori posto è segnalato")
    check(all((out / ("%s.md" % i)).is_file() for i in ids), "tutte le fonti dell'elenco sono estratte")


def regressions(tmp):
    print("Casi di regressione")
    import importlib.util
    sys.dont_write_bytecode = True  # niente __pycache__ dentro la skill
    spec = importlib.util.spec_from_file_location("extract_sources", SCRIPTS / "extract_sources.py")
    es = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(es)
    body = "testo di prova abbastanza lungo per una lezione. " * 12
    parts, _ = es.split_lessons("Lezione 1: Introduzione\n%s\nLezione 2: Modelli\n%s" % (body, body))
    check([p[0] for p in parts] == [1, 2], "titoli 'Lezione N: titolo' senza timestamp dividono il file")
    parts, _ = es.split_lessons("## Lecture 3: Search\n%s\n## Lecture 4: Games\n%s" % (body, body))
    check([p[0] for p in parts] == [3, 4], "titoli inglesi '## Lecture N' conservano il numero")
    names = ["appello_2024-01-10.pdf", "appello_2024-01-10_soluzioni.pdf",
             "appello_2024-01-31.pdf", "appello_2024-01-31_soluzioni.pdf", "Energia_solare_giugno_2025.pdf"]
    out, _ = es.exam_ids([Path(n) for n in names])
    ids = {i for i, _ in out}
    check({"E2024-01a-sol", "E2024-01b-sol", "E2024-01a", "E2024-01b", "E2025-06"} <= ids,
          "soluzioni abbinate ai due appelli dello stesso mese; 'solare' non è una soluzione")
    # una sola trascrizione con il numero nel nome: T05, non T01
    corso = tmp / "singola"
    (corso / "slide").mkdir(parents=True)
    (corso / "trascrizioni").mkdir()
    (corso / "trascrizioni" / "lezione05.txt").write_text("Lezione 5: Test\n" + body, encoding="utf-8")
    proc = run(SCRIPTS / "extract_sources.py", "--out", tmp / "singola" / "dispensa" / "_fonti", "--corso", corso)
    elenco = (corso / "dispensa" / "elenco.txt").read_text(encoding="utf-8") if (corso / "dispensa" / "elenco.txt").exists() else ""
    check(proc.returncode == 0 and (tmp / "singola" / "dispensa" / "_fonti" / "T05.md").is_file(),
          "una sola trascrizione 'lezione05' prende il numero 5")
    # cartelle con trattini, layout per modulo, file di blocco di Office, formati non supportati
    check(es.folder_kind("Slide-del-corso") == "S" and es.folder_kind("esami-vecchi") == "E",
          "cartelle 'Slide-del-corso' ed 'esami-vecchi' riconosciute")
    layout = tmp / "layout"
    (layout / "modulo1" / "slide").mkdir(parents=True)
    run(ROOT / "evals" / "make_fixtures.py", "--cartelle", tmp / "base")
    (layout / "modulo1" / "slide" / "01_intro.pdf").write_bytes((tmp / "base" / "slide" / "01_sistemi_dinamici.pdf").read_bytes())
    (layout / "Slide-del-corso").mkdir()
    (layout / "Slide-del-corso" / "~$lez07.pptx").write_bytes(b"lock")
    (layout / "Slide-del-corso" / "vecchia.ppt").write_bytes(b"binario")
    proc = run(SCRIPTS / "extract_sources.py", "--out", layout / "dispensa" / "_fonti", "--corso", layout)
    elenco = (layout / "dispensa" / "elenco.txt").read_text(encoding="utf-8") if (layout / "dispensa" / "elenco.txt").exists() else ""
    check("~$" not in elenco and "lez07" not in elenco, "il file di blocco ~$ viene ignorato")
    check("vecchia.ppt" in proc.stdout + elenco, "il .ppt non supportato viene segnalato")
    check("modulo1/slide/01_intro.pdf" in elenco, "layout modulo1/slide riconosciuto come slide")
    # il report dei tag conserva i valori tra `backtick` (strip_code li cancella solo per la ricerca)
    spec2 = importlib.util.spec_from_file_location("check_coverage", SCRIPTS / "check_coverage.py")
    cc = importlib.util.module_from_spec(spec2)
    spec2.loader.exec_module(cc)
    cap = tmp / "cap-tag.md"
    cap.write_text("# 3 Primo ordine\n\n## 3.3 Assestamento\n\n[INTEGRAZIONE: il valore è `ln(50)·τ ≈ 3,9τ`.]\n",
                   encoding="utf-8")
    inv = cc.tag_inventory([cap])
    testo = inv["INTEGRAZIONE"][0][2] if inv.get("INTEGRAZIONE") else ""
    check("ln(50)" in testo, "il report dei tag conserva i valori tra backtick")


def ids_of(elenco, root, cwd):
    """{percorso nel corso: ID} dall'elenco scritto da --corso lanciato da cwd."""
    out = {}
    for l in elenco.read_text(encoding="utf-8").splitlines():
        if "=" in l and not l.startswith("#"):
            sid, path = l.split("=", 1)
            out[(cwd / path).relative_to(root).as_posix()] = sid
    return out


def corso_run(root, cwd=None, corso=None):
    """extract_sources.py --corso lanciato da cwd (di default il corso stesso) con dispensa/ lì dentro:
    restituisce (processo, {percorso nel corso: ID})."""
    cwd = Path(cwd or root)
    proc = subprocess.run([sys.executable, str(SCRIPTS / "extract_sources.py"), "--out", "dispensa/_fonti",
                           "--corso", str(corso or root)], capture_output=True, text=True, cwd=str(cwd))
    if proc.returncode:
        print(proc.stdout[-2000:], proc.stderr[-2000:], sep="\n")
    return proc, ids_of(cwd / "dispensa" / "elenco.txt", cwd / (corso or root), cwd)


def modules(tmp):
    print("Moduli con file dallo stesso nome")
    run(ROOT / "evals" / "make_fixtures.py", "--cartelle", tmp / "base")
    pdfs = [p.read_bytes() for p in sorted((tmp / "base").rglob("*.pdf"))]  # cinque PDF diversi

    def put(path, k):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(pdfs[k])

    corso = tmp / "corso"
    for k, m in enumerate(("modulo1", "modulo2")):
        put(corso / m / "slide" / "01_intro.pdf", 2 * k)
        put(corso / m / "slide" / "02_modelli.pdf", 2 * k + 1)
    proc, ids = corso_run(corso)
    check(proc.returncode == 0 and all((corso / "dispensa" / "_fonti" / ("%s.md" % i)).is_file()
                                       for i in ("S1-01", "S1-02", "S2-01", "S2-02")),
          "modulo1/slide/01_intro.pdf e modulo2/slide/01_intro.pdf estratti come due fonti")
    proc, again = corso_run(corso)
    check(proc.returncode == 0 and again == ids, "rilanciando --corso i moduli tengono i loro ID")
    # corso spostato (o riallegato in una chat nuova) con un modulo in più che sposta la numerazione
    spostato = tmp / "spostato"
    corso.rename(spostato)
    put(spostato / "modulo0" / "slide" / "01_intro.pdf", 4)
    proc, moved = corso_run(spostato)
    check(proc.returncode == 0 and all(moved.get(p) == i for p, i in ids.items())
          and moved.get("modulo0/slide/01_intro.pdf") not in set(ids.values()) | {None},
          "con il corso spostato e un modulo nuovo ogni file tiene il suo ID")

    # prima chat: solo modulo1, dispensa/ nella cartella di lavoro e percorsi assoluti nell'indice
    chat1 = tmp / "chat1"
    put(chat1 / "corso" / "modulo1" / "slide" / "01_intro.pdf", 0)
    put(chat1 / "corso" / "modulo1" / "slide" / "02_modelli.pdf", 1)
    proc, first = corso_run(chat1 / "corso", cwd=chat1, corso=chat1 / "corso")
    # un modulo per chat: un'altra chat con lo stesso lavoro ma solo modulo2
    chat3 = tmp / "chat3"
    shutil.copytree(str(chat1), str(chat3))
    shutil.rmtree(str(chat3 / "corso" / "modulo1"))
    put(chat3 / "corso" / "modulo2" / "slide" / "01_intro.pdf", 2)
    proc, alone = corso_run(chat3 / "corso", cwd=chat3, corso="corso")
    check(proc.returncode == 0 and alone.get("modulo2/slide/01_intro.pdf") not in set(first.values()) | {None},
          "un modulo da solo non prende gli ID dell'altro")
    # seconda chat: il lavoro riparte altrove (i vecchi percorsi non esistono più) e arriva modulo2
    chat2 = tmp / "chat2"
    chat1.rename(chat2)
    put(chat2 / "corso" / "modulo2" / "slide" / "01_intro.pdf", 2)
    put(chat2 / "corso" / "modulo2" / "slide" / "02_modelli.pdf", 3)
    proc, second = corso_run(chat2 / "corso", cwd=chat2, corso="corso")
    m2 = second.get("modulo2/slide/01_intro.pdf")
    check(proc.returncode == 0 and all(second.get(p) == i for p, i in first.items())
          and m2 not in set(first.values()) and (chat2 / "dispensa" / "_fonti" / ("%s.md" % m2)).is_file(),
          "in una chat nuova il modulo aggiunto viene estratto e il primo tiene i suoi ID")

    # una copia aggiornata del corso accanto a quella vecchia, con una lezione nuova
    vecchio = tmp / "vecchio"
    put(vecchio / "slide" / "01_intro.pdf", 0)
    put(vecchio / "slide" / "02_modelli.pdf", 1)
    proc, old = corso_run(vecchio)
    nuovo = tmp / "nuovo"
    shutil.copytree(str(vecchio), str(nuovo))
    put(nuovo / "slide" / "03_nuova.pdf", 2)
    proc, new = corso_run(nuovo)
    check(proc.returncode == 0 and new == dict(old, **{"slide/03_nuova.pdf": "S03"}),
          "una copia del corso tiene gli ID, la lezione nuova prende S03")
    # da slide/ piatta a moduli, sul posto: il file spostato tiene il suo ID grazie al contenuto
    shutil.rmtree(str(nuovo / "dispensa"))
    shutil.rmtree(str(nuovo / "slide"))
    put(nuovo / "slide" / "01_intro.pdf", 0)
    corso_run(nuovo)
    (nuovo / "modulo1").mkdir()
    (nuovo / "slide").rename(nuovo / "modulo1" / "slide")
    put(nuovo / "modulo2" / "slide" / "01_intro.pdf", 2)
    proc, split = corso_run(nuovo)
    check(proc.returncode == 0 and split.get("modulo1/slide/01_intro.pdf") == "S01"
          and split.get("modulo2/slide/01_intro.pdf") not in ("S01", None),
          "riorganizzando slide/ in moduli il file spostato tiene S01")


def change_id(tmp):
    print("Cambio di ID come descritto in source-registry.md")
    run(ROOT / "evals" / "make_fixtures.py", tmp / "corso")
    fonti, lista = tmp / "_fonti", tmp / "elenco.txt"
    s1, s2 = tmp / "corso" / "lez01_sistemi.pdf", tmp / "corso" / "lez02_primo_ordine.pdf"
    lista.write_text("S01=%s\nS02=%s\n" % (s1, s2), encoding="utf-8")
    run(SCRIPTS / "extract_sources.py", "--out", fonti, "--lista", lista)
    run(SCRIPTS / "visual.py", "note", "--fonti", fonti, "S01", "5", "Schema a blocchi: u(t), sistema, y(t)")
    lista.write_text("S01=%s\nS03=%s\n" % (s1, s2), encoding="utf-8")
    (fonti / "S02.md").unlink()
    proc = run(SCRIPTS / "extract_sources.py", "--out", fonti, "--lista", lista)
    index = (fonti / "_indice.json").read_text(encoding="utf-8")
    check(proc.returncode == 0 and (fonti / "S03.md").is_file() and '"S02"' not in index,
          "cancellato _fonti/S02.md, il file viene estratto come S03")
    check("(lettura visiva)" in (fonti / "S01.md").read_text(encoding="utf-8"),
          "la lettura visiva di S01 resta dopo il cambio di ID")
    registry = (SKILL / "references" / "source-registry.md").read_text(encoding="utf-8")
    check(not re.search(r"--lista[^`]*--force", registry), "source-registry.md non suggerisce --lista con --force")


def text_pdf(path, pages):
    """Un PDF con una riga di testo per ogni stringa di ogni pagina."""
    try:
        import pymupdf as fitz
    except ImportError:
        import fitz
    doc = fitz.open()
    for lines in pages:
        page = doc.new_page(width=842, height=474)
        for k, line in enumerate(lines):
            page.insert_text((40, 60 + 30 * k), line, fontsize=16)
    doc.save(str(path))


def coverage(tmp):
    print("Copertura: intervalli ampi, slide di servizio, esercizi")
    run(ROOT / "evals" / "make_fixtures.py", tmp / "corso")
    corso, fonti = tmp / "corso", tmp / "_fonti"
    # due slide Beamer con quattro passi di animazione ciascuna: otto pagine, due slide distinte
    text_pdf(corso / "lez03_beamer.pdf", [[t] + ["Punto %d di %s: abbastanza testo per la slide" % (k, t.lower())
                                                 for k in range(1, step + 1)]
                                          for t in ("Stabilità dei sistemi", "Poli e zeri") for step in range(1, 5)])
    # quattro slide di contenuto e le quattro slide di servizio del modello: titolo, indice, domande, grazie
    content = ["Contenuto %d: una definizione con abbastanza testo da spiegare nella dispensa" % k for k in range(4)]
    text_pdf(corso / "lez04_breve.pdf", [["Lez. 4"], ["Indice"]] + [[c] for c in content] + [["Domande?"], ["Grazie"]])
    run(SCRIPTS / "extract_sources.py", "--out", fonti, "S01=%s" % (corso / "lez01_sistemi.pdf"),
        "S02=%s" % (corso / "lez02_primo_ordine.pdf"), "S03=%s" % (corso / "lez03_beamer.pdf"),
        "S04=%s" % (corso / "lez04_breve.pdf"), "E2025-06=%s" % (corso / "esame_2025-06-16.pdf"))
    book = tmp / "capitoli"
    book.mkdir()

    def check_book(text, *extra, expect=0):
        (book / "01.md").write_text(text, encoding="utf-8")
        return run(SCRIPTS / "check_coverage.py", "--fonti", fonti, "--libro", book, "--solo", "S01,S03,E", *extra,
                   expect=expect)

    def warned(proc):
        return proc.stdout.split("AVVISI")[1].split("COPERTURA")[0]

    beamer = " Animazioni [S03, slide 1-8]. Es. [E2025-06, es. 1].\n"
    proc = check_book("# 1\n\nTutto [S01, slide 1-6]." + beamer)
    check(proc.returncode == 0 and "S01: slide 1-6 coperte solo da citazioni a più di" in proc.stdout,
          "un intervallo di 6 slide distinte viene segnalato")
    check("S03:" not in warned(proc), "otto passi di due animazioni Beamer non sono un intervallo ampio")
    proc = check_book("# 1\n\nQuattro [S01, slide 1-4]. Due [S01, slide 5-6]." + beamer)
    check(proc.returncode == 0 and "AVVISI (0)" in proc.stdout, "un intervallo di 4 slide non viene segnalato")
    proc = check_book("# 1\n\nCinque [S01, slide 1-5]. Una [S01, slide 6]." + beamer)
    check("S01: slide 1-5 coperte solo" in proc.stdout, "un intervallo di 5 slide viene segnalato")
    proc = check_book("# 1\n\nTutto [S01, slide 1-3]; [S01, slide 4-6]. Due [S01, slide 1; S01, slide 2-6]." + beamer)
    check("S01: slide 1-6 coperte solo" in proc.stdout and "01.md:3" in proc.stdout,
          "un intervallo diviso in citazioni attaccate viene segnalato")
    proc = check_book("# 1\n\nUno [S01, slide 1]. Due [S01, slide 2]. Tre [S01, slide 3]. Quattro [S01, slide 4]. "
                      "Cinque [S01, slide 5]. Sei [S01, slide 6]." + beamer)
    check(proc.returncode == 0 and "AVVISI (0)" in proc.stdout,
          "un paragrafo con una citazione per frase non viene segnalato")
    for k in range(1, 9):
        run(SCRIPTS / "visual.py", "note", "--fonti", fonti, "S03", str(k), "Grafico, passo %d" % k)
    proc = check_book("# 1\n\nUno [S01, slide 2]. Due [S01, slide 3-4]." + beamer
                      + "\n# Appendici\n\n## F. Slide di servizio\n\n[S01, slide 1, 5-6]\n")
    check(proc.returncode == 0 and "AVVISI (0)" in proc.stdout,
          "citazioni mirate, slide di servizio e animazioni con letture visive non vengono segnalate")
    proc = check_book("# 1\n" + beamer + "\n## Slide di servizio\n\n[S01, slide 1-6]\n")
    check("su 6, con del testo, coperte solo da «Slide di servizio»" in proc.stdout,
          "un file coperto solo dalle slide di servizio viene segnalato")
    (book / "01.md").write_text("# 4\n\n" + " ".join("Uno [S04, slide %d]." % k for k in range(3, 7))
                                + "\n\n## F. Slide di servizio\n\n[S04, slide 1-2, 7-8]\n", encoding="utf-8")
    proc = run(SCRIPTS / "check_coverage.py", "--fonti", fonti, "--libro", book, "--solo", "S04")
    check(proc.returncode == 0 and "AVVISI (0)" in proc.stdout,
          "titolo, indice, «Domande?» e «Grazie» tra le slide di servizio non vengono segnalati")
    with open(str(fonti / "S03.md"), "ab") as f:  # una nota salvata da un editor in cp1252
        f.write("\n(lettura visiva) \xe8 importante\n".encode("cp1252"))
    proc = check_book("# 1\n\nUno [S01, slide 1-2]. Due [S01, slide 3-4]. Tre [S01, slide 5-6]." + beamer)
    check(proc.returncode == 0 and "Esito: ✓" in proc.stdout, "un file di _fonti/ non UTF-8 non ferma il controllo")

    proc = check_book("# 1\n\n[S01, slide 1-2]. [S01, slide 3-4]. [S01, slide 5-6]. [S03, slide 1-8].\n\n"
                      "Esempio [E2025-06, esempio 3].\n", expect=1)
    check(proc.returncode == 1 and "[E2025-06, esempio 3]: posizione non riconosciuta" in proc.stdout,
          "«esempio 3» non è scambiato per l'esercizio «empio 3»")
    proc = check_book("# 1\n\n[S01, slide 1-2]. [S01, slide 3-4]. [S01, slide 5-6]. [S03, slide 1-8].\n\n"
                      "Esercizi [E2025-06, esercizi 1-3]. Domande [E2025-06, domande 2]. A [E2025-06, dom.A].\n")
    check(proc.returncode == 0 and "ERRORI (0)" in proc.stdout,
          "«esercizi 1-3», «domande 2» e «dom.A» restano citazioni di esercizi")
    esercizi = tmp / "esercizi.md"
    esercizi.write_text("| Rif. |\n|---|\n| [E2025-06, es. 1] |\n", encoding="utf-8")
    proc = check_book("# 1\n\n[S01, slide 1-2]. [S01, slide 3-4]. [S01, slide 5-6]. [S03, slide 1-8].\n\n"
                      "Es. [E2025-06, esercizio 1], parte a [E2025-06, es. 1a], e [E2025-06, es. 9].\n",
                      "--esercizi", esercizi)
    check(proc.returncode == 0 and "[E2025-06, es. 9] citato ma assente da esercizi.md" in proc.stdout
          and "es. 1] citato" not in proc.stdout and "es. 1a] citato" not in proc.stdout,
          "un esercizio citato ma assente dal catalogo viene segnalato, una sua parte no")


def resume(tmp):
    print("Riprendere il lavoro: nomi semplici, cartelle rinominate, file cambiati")
    run(ROOT / "evals" / "make_fixtures.py", tmp / "fx")
    run(ROOT / "evals" / "make_fixtures.py", "--cartelle", tmp / "fxc")
    pdfs = [p.read_bytes() for p in sorted((tmp / "fxc").rglob("*.pdf"))]
    es = [sys.executable, str(SCRIPTS / "extract_sources.py"), "--out", "dispensa/_fonti"]

    def here(cwd, *args):
        return subprocess.run(es + list(args), capture_output=True, text=True, cwd=str(cwd))

    # cartella senza sottocartelle, comandi lanciati da lì con i soli nomi dei file
    flat = tmp / "piatta"
    flat.mkdir()
    for name in ("lez01_sistemi.pdf", "lez02_primo_ordine.pdf", "trascrizioni_lezioni.docx"):
        shutil.copy(str(tmp / "fx" / name), str(flat / name))
    shutil.copy(str(tmp / "fxc" / "altro" / "programma.pdf"), str(flat / "programma.pdf"))
    args = ("S01=lez01_sistemi.pdf", "S02=./lez02_primo_ordine.pdf", "X01=programma.pdf", "T=trascrizioni_lezioni.docx")
    here(flat, *args)
    proc = here(flat, *args)
    check(proc.returncode == 0 and "✗" not in proc.stdout + proc.stderr,
          "rilanciando con i soli nomi dei file le fonti già estratte vengono saltate")
    proc = here(flat, "S03=lez01_sistemi.pdf")
    check(proc.returncode == 1 and "già registrato come S01" in proc.stderr, "lo stesso file con un altro ID viene rifiutato")
    shutil.copy(str(flat / "programma.pdf"), str(flat / "copia.pdf"))
    proc = here(flat, "X02=copia.pdf", "X03=copia.pdf")
    check(proc.returncode == 1 and "già registrato come X02" in proc.stderr,
          "lo stesso file due volte nello stesso comando viene rifiutato")
    for k, sub in enumerate(("a", "b")):
        (flat / sub).mkdir()
        (flat / sub / "scheda.pdf").write_bytes(pdfs[k])
    here(flat, "X05=a/scheda.pdf")
    proc = here(flat, "X06=b/scheda.pdf")
    check(proc.returncode == 0 and (flat / "dispensa" / "_fonti" / "X06.md").is_file(),
          "due file con lo stesso nome in cartelle diverse sono due fonti anche senza --corso")

    # cartella del modulo rinominata: i file non cambiano, gli ID nemmeno
    corso = tmp / "corso"
    for k, name in enumerate(("01_intro.pdf", "02_modelli.pdf")):
        (corso / "modulo1" / "slide").mkdir(parents=True, exist_ok=True)
        (corso / "modulo1" / "slide" / name).write_bytes(pdfs[k])
    (corso / "trascrizioni").mkdir()
    shutil.copy(str(tmp / "fx" / "trascrizioni_lezioni.txt"), str(corso / "trascrizioni" / "tutte.txt"))
    proc, before = corso_run(corso)
    (corso / "modulo1").rename(corso / "Modulo 1 - Fondamenti")
    proc, after = corso_run(corso)
    check(proc.returncode == 0 and after.get("Modulo 1 - Fondamenti/slide/01_intro.pdf") == before["modulo1/slide/01_intro.pdf"]
          and after.get("Modulo 1 - Fondamenti/slide/02_modelli.pdf") == before["modulo1/slide/02_modelli.pdf"],
          "rinominando la cartella del modulo ogni file tiene il suo ID")
    # spostando il corso, le trascrizioni divise da un solo file restano T01 e T02
    corso.rename(tmp / "corso-spostato")
    corso = tmp / "corso-spostato"
    proc, moved = corso_run(corso)
    check(proc.returncode == 0 and all((corso / "dispensa" / "_fonti" / ("T0%d.md" % k)).is_file() for k in (1, 2))
          and "✗" not in proc.stdout + proc.stderr, "con il corso spostato le lezioni divise da T= restano T01 e T02")
    # un file già estratto che cambia contenuto: segnalato, e l'indice non lo scambia per un altro
    target = corso / "Modulo 1 - Fondamenti" / "slide" / "01_intro.pdf"
    target.write_bytes(pdfs[2])
    proc, changed = corso_run(corso)
    check(proc.returncode == 0 and "01_intro.pdf è cambiato da quando è stato estratto" in proc.stdout,
          "un file già estratto che cambia contenuto viene segnalato")

    # da slide/ piatta a moduli, quando l'ordine alfabetico e il contenuto non coincidono
    d = tmp / "riordino"
    (d / "slide").mkdir(parents=True)
    (d / "slide" / "01_intro.pdf").write_bytes(pdfs[0])
    corso_run(d)
    (d / "modulo2").mkdir()
    (d / "slide").rename(d / "modulo2" / "slide")
    (d / "modulo1" / "slide").mkdir(parents=True)
    (d / "modulo1" / "slide" / "01_intro.pdf").write_bytes(pdfs[3])
    # un elenco scritto a mano che dà S01 al file sbagliato (anche lui finisce con slide/01_intro.pdf) viene rifiutato
    lista = d / "sbagliato.txt"
    lista.write_text("# Elenco preparato da extract_sources.py --corso .\nS01=modulo1/slide/01_intro.pdf\n"
                     "S07=modulo2/slide/01_intro.pdf\n", encoding="utf-8")
    proc = here(d, "--lista", str(lista))
    check(proc.returncode == 1 and "S01: ID già usato" in proc.stderr, "un ID dato al file sbagliato viene rifiutato")
    proc, split = corso_run(d)
    check(proc.returncode == 0 and split.get("modulo2/slide/01_intro.pdf") == "S01"
          and split.get("modulo1/slide/01_intro.pdf") not in ("S01", None),
          "riorganizzando in moduli S01 resta al file con lo stesso contenuto, non al primo in ordine")

    # in una chat nuova arriva solo la cartella di un modulo, come corso a sé: prende l'ID di quel modulo
    parte = tmp / "parte"
    shutil.copytree(str(d / "modulo1"), str(parte / "corso"))
    shutil.copytree(str(d / "dispensa"), str(parte / "dispensa"))
    proc, alone = corso_run(parte / "corso", cwd=parte, corso="corso")
    check(proc.returncode == 0 and alone.get("slide/01_intro.pdf") == split["modulo1/slide/01_intro.pdf"],
          "una cartella con un solo modulo prende l'ID del suo modulo, deciso dal contenuto")
    # il corso dentro una cartella in più, con un file aggiornato: tiene l'ID e lo segnala
    wrap = tmp / "wrap"
    shutil.copytree(str(d), str(wrap / "mio-corso"))
    shutil.move(str(wrap / "mio-corso" / "dispensa"), str(wrap / "dispensa"))
    (wrap / "mio-corso" / "modulo2" / "slide" / "01_intro.pdf").write_bytes(pdfs[4])
    proc, wrapped = corso_run(wrap, cwd=wrap, corso=".")
    check(proc.returncode == 0 and wrapped.get("mio-corso/modulo2/slide/01_intro.pdf") == "S01"
          and "01_intro.pdf è cambiato" in proc.stdout,
          "con una cartella in più un file aggiornato tiene il suo ID e viene segnalato")

    # indice di una versione precedente (senza contenuto): se due file somigliano a S01 lo stesso modo, lo dice
    old_ix = tmp / "vecchio-indice"
    (old_ix / "slide").mkdir(parents=True)
    (old_ix / "slide" / "01_intro.pdf").write_bytes(pdfs[0])
    corso_run(old_ix)
    ix_path = old_ix / "dispensa" / "_fonti" / "_indice.json"
    ix = json.loads(ix_path.read_text(encoding="utf-8"))
    for v in ix.values():
        v.pop("sha1", None)
        v.pop("rel", None)
    ix_path.write_text(json.dumps(ix), encoding="utf-8")
    for m in ("modulo1", "modulo2"):
        (old_ix / m / "slide").mkdir(parents=True)
        shutil.copy(str(old_ix / "slide" / "01_intro.pdf"), str(old_ix / m / "slide" / "01_intro.pdf"))
    shutil.rmtree(str(old_ix / "slide"))
    proc, _ = corso_run(old_ix)
    check(proc.returncode == 0 and "S01 (01_intro.pdf) corrisponde allo stesso modo" in proc.stdout,
          "un ID che due file reclamano allo stesso modo viene segnalato")

    # cambio di ID partendo dall'elenco scritto da --corso: il file riestratto ha il percorso nel corso
    elenco = d / "dispensa" / "elenco.txt"
    old = split["modulo1/slide/01_intro.pdf"]
    elenco.write_text(elenco.read_text(encoding="utf-8").replace("%s=" % old, "S09="), encoding="utf-8")
    (d / "dispensa" / "_fonti" / ("%s.md" % old)).unlink()
    proc = here(d, "--lista", "dispensa/elenco.txt")
    index = json.loads((d / "dispensa" / "_fonti" / "_indice.json").read_text(encoding="utf-8"))
    check(proc.returncode == 0 and index.get("S09", {}).get("rel") == "modulo1/slide/01_intro.pdf",
          "con l'elenco di --corso il nuovo ID conosce il percorso nel corso")


def coverage_more(tmp):
    print("Copertura: letture visive, animazioni in una riga, gruppi, sottosezioni, catalogo")
    run(ROOT / "evals" / "make_fixtures.py", tmp / "corso")
    corso, fonti = tmp / "corso", tmp / "_fonti"
    content = ["Contenuto %d: una definizione con abbastanza testo da spiegare nella dispensa" % k for k in range(4)]
    text_pdf(corso / "breve.pdf", [["Lez. 4"], ["Indice"], ["Parte 1"]] + [[c] for c in content] + [["Domande?"], ["Grazie"]])
    # una definizione scritta parola per parola con \pause: la riga si allunga a ogni passo
    words = "Un sistema è asintoticamente stabile se tutti i poli hanno parte reale negativa".split()
    text_pdf(corso / "pause.pdf", [["Stabilità asintotica", " ".join(words[:k])] for k in range(3, len(words) + 1, 2)])
    run(SCRIPTS / "extract_sources.py", "--out", fonti, "S01=%s" % (corso / "lez01_sistemi.pdf"),
        "S04=%s" % (corso / "breve.pdf"), "S05=%s" % (corso / "pause.pdf"),
        "E2025-06=%s" % (corso / "esame_2025-06-16.pdf"), "E2025-06-sol=%s" % (corso / "esame_2025-09-10.pdf"))
    n5 = len(json.loads((fonti / "_indice.json").read_text(encoding="utf-8"))["S05"]["labels"])
    for k in (1, 2, 3, 8, 9):
        run(SCRIPTS / "visual.py", "note", "--fonti", fonti, "S04", str(k), "nessun contenuto da spiegare")
    book = tmp / "capitoli"
    book.mkdir()

    def check_book(text, *extra):
        (book / "01.md").write_text(text, encoding="utf-8")
        return run(SCRIPTS / "check_coverage.py", "--fonti", fonti, "--libro", book, *extra)

    s01 = "Uno [S01, slide 1-2]. Due [S01, slide 3-4]. Tre [S01, slide 5-6]."
    es = " Es. [E2025-06, es. 1]."
    proc = check_book("# 1\n\n" + s01 + es + " La definizione [S05, slide 1-%d]. " % n5
                      + " ".join("Punto [S04, slide %d]." % k for k in range(4, 8))
                      + "\n\n## F. Slide di servizio\n\n### Lezione 4\n\n[S04, slide 1-3, 8-9]\n")
    check(proc.returncode == 0 and "AVVISI (0)" in proc.stdout,
          "slide di servizio con letture visive, un'animazione con \\pause e una sottosezione non vengono segnalate")
    # un titolo e quattro indici uguali (uno a ogni sezione) tra le slide di servizio non sono contenuto nascosto
    toc = ["1. Introduzione ai sistemi dinamici", "2. Sistemi del primo ordine", "3. Risposta in frequenza"]
    text_pdf(corso / "indici.pdf", [["Sistemi dinamici", "Prof. Mario Rossi, anno accademico 2025/26"]] + [toc] * 4
             + [[content[0]], [content[1]]])
    run(SCRIPTS / "extract_sources.py", "--out", tmp / "_fonti_indici", "S06=%s" % (corso / "indici.pdf"))
    (book / "01.md").write_text("# 6\n\nUno [S06, slide 6]. Due [S06, slide 7].\n\n## F. Slide di servizio\n\n"
                                "[S06, slide 1-5]\n", encoding="utf-8")
    proc = run(SCRIPTS / "check_coverage.py", "--fonti", tmp / "_fonti_indici", "--libro", book)
    check(proc.returncode == 0 and "AVVISI (0)" in proc.stdout,
          "gli indici ripetuti a ogni sezione tra le slide di servizio non vengono segnalati")
    proc = check_book("# 1\n\nUno [S01, slide 1-3]. [S01, slide 4-6].\n\nDue [S01, slide 1-3] e [S01, slide 4-6]."
                      + es + " [S05, slide 1-%d]. [S04, slide 1-4]. [S04, slide 5-9].\n" % n5)
    check(proc.stdout.count("S01: slide 1-6 coperte solo") == 1 and "01.md:3" in proc.stdout and "01.md:5" in proc.stdout,
          "citazioni separate da un punto o da «e» contano insieme")
    proc = check_book("# 1\n\nTutto [S01, slide 1-5].\n\nAltro [S01, slide 2-6]. Due [S01, slide 2]. Tre [S01, slide 3]. "
                      "Quattro [S01, slide 4]. Cinque [S01, slide 5]. Sei [S01, slide 6]." + es
                      + " [S05, slide 1-%d]. [S04, slide 1-4]. [S04, slide 5-9].\n" % n5)
    check("S01: slide 1 coperta solo" in proc.stdout and "(01.md:3)" in proc.stdout,
          "l'avviso nomina solo la citazione che contiene la slide, al singolare")
    esercizi = tmp / "esercizi.md"
    esercizi.write_text("| Rif. |\n|---|\n| [E2025-06, es. 1a] |\n| [E2025-06, es. 1b] |\n", encoding="utf-8")
    proc = check_book("# 1\n\n" + s01 + " [S05, slide 1-%d]. [S04, slide 1-4]. [S04, slide 5-9].\n\n" % n5
                      + "Es. [E2025-06, es. 1a] e [E2025-06, es. 1b], intero [E2025-06, es. 1], "
                      "soluzione [E2025-06-sol, es. 1].\n", "--esercizi", esercizi)
    check(proc.returncode == 0 and "citato ma assente" not in proc.stdout,
          "parti di un esercizio e soluzioni non vengono segnalate come assenti dal catalogo")


def main():
    frontmatter()
    with tempfile.TemporaryDirectory() as tmp:
        scripts(Path(tmp))
    with tempfile.TemporaryDirectory() as tmp:
        folders(Path(tmp))
    with tempfile.TemporaryDirectory() as tmp:
        regressions(Path(tmp))
    for test in (modules, change_id, coverage, resume, coverage_more):
        with tempfile.TemporaryDirectory() as tmp:
            test(Path(tmp))
    print("\n%s" % ("✗ %d controlli falliti" % len(failures) if failures else "✓ tutto a posto"))
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
