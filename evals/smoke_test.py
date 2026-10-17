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

import re
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


def main():
    frontmatter()
    with tempfile.TemporaryDirectory() as tmp:
        scripts(Path(tmp))
    with tempfile.TemporaryDirectory() as tmp:
        folders(Path(tmp))
    with tempfile.TemporaryDirectory() as tmp:
        regressions(Path(tmp))
    print("\n%s" % ("✗ %d controlli falliti" % len(failures) if failures else "✓ tutto a posto"))
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
