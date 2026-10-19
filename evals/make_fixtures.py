#!/usr/bin/env python3
"""Crea un piccolo corso di prova per le eval della skill slide-to-book.

Uso:
    python3 evals/make_fixtures.py <cartella>              # tutti i file in una cartella
    python3 evals/make_fixtures.py --cartelle <cartella>   # slide/, trascrizioni/, esami/, altro/
    python3 evals/make_fixtures.py --pptx <file.pptx>      # una presentazione PPTX di prova

Senza --cartelle scrive due PDF di slide (12 slide in tutto, una solo-diagramma), le
trascrizioni di due lezioni nello stesso file (DOCX e, uguale, TXT) e due esami in PDF:
è ciò che arriva quando si allegano i file in chat. Con --cartelle scrive lo stesso corso come
lo organizza uno studente: una trascrizione per lezione (TXT e DOCX), una
registrazione audio non ancora trascritta, gli esami con la data nel nome e le
soluzioni ufficiali di un appello, il programma del corso e un file fuori posto.
Il contenuto è inventato ma coerente, così le eval possono controllare copertura,
priorità, tag e risultati numerici. Serve PyMuPDF (pip install pymupdf).
"""

import sys
import zipfile
from pathlib import Path

try:
    import pymupdf as fitz  # PyMuPDF 1.24.3 e successive
except ImportError:
    import fitz  # versioni precedenti di PyMuPDF

W, H = 842, 474  # 16:9

CSS = "body{font-family:sans-serif;font-size:20px} h1{font-size:34px} h2{font-size:28px} li{margin:6px 0}"

SLIDES = {
    "lez01_sistemi.pdf": [
        "<h1>Corso di prova</h1><p>Lezione 1: sistemi dinamici</p><p>Materiale fittizio per le prove della skill</p>",
        "<h2>Sistema dinamico</h2><ul><li>Un sistema dinamico lega un ingresso u(t) a un'uscita y(t)</li>"
        "<li>L'uscita all'istante t dipende anche dagli ingressi passati</li><li>La memoria del sistema è lo stato x(t)</li></ul>",
        "<h2>Ingresso, stato, uscita</h2><ul><li>Equazione di stato: ẋ(t) = f(x(t), u(t))</li>"
        "<li>Trasformazione d'uscita: y(t) = g(x(t), u(t))</li><li>Esempio: auto, stato = velocità, ingresso = forza</li></ul>",
        "<h2>Sistemi lineari tempo-invarianti (LTI)</h2><ul><li>Lineare: vale la sovrapposizione degli effetti</li>"
        "<li>Tempo-invariante: un ritardo dell'ingresso ritarda l'uscita della stessa quantità</li>"
        "<li>Forma: ẋ = A x + B u, y = C x + D u</li></ul>",
        None,  # slide solo-diagramma
        "<h2>Teorema di esistenza e unicità (cenni)</h2><ul><li>Se f è lipschitziana, la soluzione esiste ed è unica</li>"
        "<li>Dimostrazione: vedi testo consigliato</li></ul>",
    ],
    "lez02_primo_ordine.pdf": [
        "<h1>Corso di prova</h1><p>Lezione 2: sistemi del primo ordine</p>",
        "<h2>Sistema del primo ordine</h2><ul><li>Funzione di trasferimento: G(s) = K / (1 + τ s)</li>"
        "<li>K: guadagno statico</li><li>τ: costante di tempo, in secondi</li></ul>",
        "<h2>Risposta al gradino</h2><ul><li>Ingresso: gradino di ampiezza A</li>"
        "<li>y(t) = A K (1 − e<sup>−t/τ</sup>) per t ≥ 0</li><li>Valore finale: A K</li></ul>",
        "<h2>Tempo di assestamento</h2><ul><li>Al 2%: t<sub>a</sub> ≈ 4τ</li><li>All'1%: t<sub>a</sub> ≈ 4.6τ</li>"
        "<li>Dopo un tempo τ l'uscita è al 63% del valore finale</li></ul>",
        "<h2>Esempio: circuito RC</h2><ul><li>Ingresso: tensione del generatore; uscita: tensione sul condensatore</li>"
        "<li>K = 1, τ = R C</li><li>R = 10 kΩ, C = 10 µF ⇒ τ = 0.1 s</li></ul>",
        "<h1>Grazie</h1><p>Domande?</p>",
    ],
}

LESSONS = [
    ("Lezione 1", [
        "Buongiorno a tutti, iniziamo il corso. Prima la logistica: gli orari di ricevimento sono sulla pagina del corso.",
        "Allora, l'esame. Lo scritto ha tre esercizi e dura due ore, e non è ammesso il formulario: le formule vanno sapute.",
        "Partiamo dalla slide due. Un sistema dinamico è qualcosa che trasforma un ingresso in un'uscita, ma con memoria: l'uscita di adesso dipende anche da cosa è successo prima.",
        "Pensate a una tazza di caffè che si raffredda: la temperatura di adesso dipende da quella di un minuto fa. Quella memoria è lo stato.",
        "Nella slide tre vedete l'equazione di stato e la trasformazione d'uscita. L'esempio dell'auto: lo stato è la velocità, l'ingresso è la forza del motore.",
        "Attenzione a non confondere stato e uscita: l'uscita è quello che misuriamo, lo stato è quello che il sistema ricorda. Possono coincidere, ma non è detto.",
        "Slide quattro, i sistemi lineari tempo-invarianti. Lineare vuol dire che vale la sovrapposizione degli effetti: la risposta alla somma di due ingressi è la somma delle risposte.",
        "La sovrapposizione degli effetti è fondamentale: all'esame la chiedo quasi sempre come domanda teorica, quindi sappiatela enunciare bene e sappiate dire perché vale solo per i sistemi lineari.",
        "Tempo-invariante vuol dire che se ritardo l'ingresso di due secondi, l'uscita è la stessa di prima, solo ritardata di due secondi. Un sistema che invecchia, per esempio, non è tempo-invariante.",
        "Nello schema a blocchi della slide cinque la freccia a sinistra è l'ingresso u(t), il blocco in mezzo è il sistema con il suo stato, e la freccia a destra è l'uscita y(t).",
        "Slide sei, il teorema di esistenza e unicità. Ve lo cito perché è la base di tutto, ma la dimostrazione non la chiedo, è solo per cultura.",
        "Per oggi è tutto. La prossima volta vediamo i sistemi del primo ordine, che sono il pane quotidiano dello scritto.",
    ]),
    ("Lezione 2", [
        "Oggi sistemi del primo ordine. Slide due: la funzione di trasferimento è K fratto uno più tau s.",
        "K è il guadagno statico: se metto un gradino unitario e aspetto, l'uscita va a K. Tau è la costante di tempo e si misura in secondi: dice quanto è lento il sistema.",
        "Slide tre, la risposta al gradino. Con un gradino di ampiezza A l'uscita vale A per K per uno meno e alla meno t su tau. Questa formula all'esame la dovete scrivere senza pensarci.",
        "Ricordatevi bene questa cosa: dopo un tempo tau l'uscita è al sessantatré per cento del valore finale. È una domanda classica.",
        "Slide quattro, il tempo di assestamento. Al due per cento è circa quattro tau, all'uno per cento circa quattro virgola sei tau.",
        "Vi dico anche una cosa che nelle slide non c'è: il tempo di salita, dal dieci al novanta per cento del valore finale, vale circa due virgola due tau. All'esame lo uso, quindi segnatevelo.",
        "Facciamo un esercizio insieme. K uguale a tre, tau uguale a due secondi, gradino unitario: quanto vale l'uscita dopo due secondi?",
        "Allora, y di due è tre per uno meno e alla meno uno, cioè circa uno virgola novanta. E il tempo di assestamento al due per cento è quattro tau, otto secondi.",
        "Questo tipo di esercizio, la risposta al gradino di un primo ordine, esce sempre allo scritto. Non c'è appello in cui non ci sia.",
        "Slide cinque, il circuito RC. La tensione sul condensatore segue proprio un primo ordine con K uguale a uno e tau uguale a R per C.",
        "Con dieci kilo-ohm e dieci microfarad viene tau uguale a zero virgola uno secondi. Occhio alle unità di misura, è l'errore che vedo di più negli scritti.",
        "Bene, ci fermiamo qui. Esercitatevi sugli appelli passati che trovate sul sito.",
    ]),
]

EXAMS = {
    "esame_2025-06-16.pdf": (
        "Corso di prova — Appello del 16 giugno 2025",
        [
            "<b>Esercizio 1.</b> Si consideri il sistema G(s) = 2 / (1 + 0.5 s), sollecitato da un gradino unitario. "
            "a) Scrivere la risposta y(t). b) Calcolare y(1). c) Determinare il tempo di assestamento al 2%.",
            "<b>Esercizio 2.</b> Enunciare il principio di sovrapposizione degli effetti e spiegare perché vale solo per i sistemi lineari.",
            "<b>Esercizio 3.</b> Un circuito RC con R = 1 kΩ e C = 100 µF è alimentato da un gradino di 5 V. "
            "Calcolare la costante di tempo e il tempo di salita (10–90%) della tensione sul condensatore.",
        ],
    ),
    "esame_2025-09-10.pdf": (
        "Corso di prova — Appello del 10 settembre 2025",
        [
            "<b>Esercizio 1.</b> Il sistema G(s) = 5 / (1 + 2 s) riceve in ingresso un gradino di ampiezza 2. "
            "Calcolare il valore finale dell'uscita, y(4) e il tempo di assestamento al 2%.",
            "<b>Esercizio 2.</b> Definire un sistema tempo-invariante e darne un esempio.",
        ],
    ),
}


def html_page(doc, html):
    page = doc.new_page(width=W, height=H)
    page.insert_htmlbox(fitz.Rect(40, 30, W - 40, H - 30), html, css=CSS)
    return page


def diagram_page(doc):
    """Slide con solo uno schema a blocchi: l'estrazione del testo trova poche parole."""
    page = doc.new_page(width=W, height=H)
    box = fitz.Rect(320, 180, 520, 290)
    page.draw_rect(box, color=(0, 0, 0), width=2)
    for x0, x1 in ((140, 320), (520, 700)):
        page.draw_line((x0, 235), (x1, 235), width=2)
        page.draw_polyline([(x1 - 12, 228), (x1, 235), (x1 - 12, 242)], width=2)
    page.insert_text((150, 225), "u(t)", fontsize=18)
    page.insert_text((395, 242), "x(t)", fontsize=18)
    page.insert_text((640, 225), "y(t)", fontsize=18)


def write_docx(path, paragraphs):
    esc = lambda s: s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    body = "".join('<w:p><w:r><w:t xml:space="preserve">%s</w:t></w:r></w:p>' % esc(p) for p in paragraphs)
    doc = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
           '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
           "<w:body>%s</w:body></w:document>" % body)
    types = ('<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
             '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
             '<Default Extension="xml" ContentType="application/xml"/>'
             '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
             "</Types>")
    rels = ('<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
            "</Relationships>")
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", types)
        z.writestr("_rels/.rels", rels)
        z.writestr("word/document.xml", doc)


P_NS = ('xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
        'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"')
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
REL_TYPE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/"


def sp(paras, ph=None):
    """Una forma con testo: paras è una lista di (livello, testo)."""
    nv = '<p:nvPr><p:ph type="%s"/></p:nvPr>' % ph if ph else "<p:nvPr/>"
    body = "".join('<a:p><a:pPr lvl="%d"/><a:r><a:t>%s</a:t></a:r></a:p>' % (lvl, txt) for lvl, txt in paras)
    return ('<p:sp><p:nvSpPr><p:cNvPr id="2" name="t"/><p:cNvSpPr/>%s</p:nvSpPr><p:spPr/>'
            '<p:txBody><a:bodyPr/>%s</p:txBody></p:sp>' % (nv, body))


def table(rows):
    cells = "".join("<a:tr>%s</a:tr>" % "".join("<a:tc><a:txBody><a:p><a:r><a:t>%s</a:t></a:r></a:p></a:txBody></a:tc>"
                                                 % c for c in row) for row in rows)
    return ('<p:graphicFrame><p:nvGraphicFramePr><p:cNvPr id="3" name="tab"/><p:cNvGraphicFramePr/><p:nvPr/>'
            '</p:nvGraphicFramePr><a:graphic><a:graphicData><a:tbl>%s</a:tbl></a:graphicData></a:graphic>'
            '</p:graphicFrame>' % cells)


def write_pptx(path):
    """Quattro slide che coprono i casi dell'estrazione PPTX: titolo ed elenco a due livelli con note del
    relatore, tabella, forme raggruppate in una slide nascosta, una slide con solo un'immagine."""
    slides = [
        (sp([(0, "Sistemi del secondo ordine")], "title")
         + sp([(0, "Pulsazione naturale e smorzamento"), (1, "smorzamento minore di 1: risposta oscillante")]),
         "Il docente: la sovraelongazione esce sempre allo scritto", ""),
        (sp([(0, "Smorzamento e sovraelongazione")], "title")
         + table([["smorzamento", "sovraelongazione"], ["0,5", "16%"], ["0,7", "5%"]]), None, ""),
        ('<p:grpSp><p:nvGrpSpPr><p:cNvPr id="4" name="g"/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr/>'
         + sp([(0, "Testo dentro un gruppo, in una slide nascosta del file originale")]) + "</p:grpSp>",
         None, ' show="0"'),
        ('<p:pic><p:nvPicPr><p:cNvPr id="5" name="img"/><p:cNvPicPr/><p:nvPr/></p:nvPicPr><p:blipFill/>'
         '<p:spPr/></p:pic>', None, ""),
    ]
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml",
                   '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/'
                   'content-types"><Default Extension="xml" ContentType="application/xml"/><Default Extension="rels" '
                   'ContentType="application/vnd.openxmlformats-package.relationships+xml"/></Types>')
        z.writestr("_rels/.rels", '<Relationships xmlns="%s"><Relationship Id="rId1" Type="%sofficeDocument" '
                   'Target="ppt/presentation.xml"/></Relationships>' % (REL_NS, REL_TYPE))
        ids = "".join('<p:sldId id="%d" r:id="rId%d"/>' % (256 + k, k) for k in range(1, len(slides) + 1))
        z.writestr("ppt/presentation.xml", "<p:presentation %s><p:sldIdLst>%s</p:sldIdLst></p:presentation>" % (P_NS, ids))
        z.writestr("ppt/_rels/presentation.xml.rels", '<Relationships xmlns="%s">%s</Relationships>' % (REL_NS, "".join(
            '<Relationship Id="rId%d" Type="%sslide" Target="slides/slide%d.xml"/>' % (k, REL_TYPE, k)
            for k in range(1, len(slides) + 1))))
        for k, (shapes, notes, show) in enumerate(slides, 1):
            z.writestr("ppt/slides/slide%d.xml" % k, "<p:sld %s%s><p:cSld><p:spTree>%s</p:spTree></p:cSld></p:sld>"
                       % (P_NS, show, shapes))
            if notes:
                z.writestr("ppt/slides/_rels/slide%d.xml.rels" % k, '<Relationships xmlns="%s"><Relationship Id="rId1" '
                           'Type="%snotesSlide" Target="../notesSlides/notesSlide%d.xml"/></Relationships>'
                           % (REL_NS, REL_TYPE, k))
                z.writestr("ppt/notesSlides/notesSlide%d.xml" % k, "<p:notes %s><p:cSld><p:spTree>%s%s</p:spTree>"
                           "</p:cSld></p:notes>" % (P_NS, sp([(0, "1")], "sldNum"), sp([(0, notes)], "body")))


SOLUTIONS = (
    "Corso di prova — Appello del 16 giugno 2025 — Soluzioni",
    [
        "<b>Esercizio 1.</b> y(t) = 2 (1 − e<sup>−2t</sup>) per t ≥ 0; y(1) = 2 (1 − e<sup>−2</sup>) ≈ 1,73; "
        "tempo di assestamento al 2%: 4τ = 2 s.",
        "<b>Esercizio 2.</b> La risposta alla somma di due ingressi è la somma delle risposte; vale solo per i "
        "sistemi lineari perché richiede additività e omogeneità.",
        "<b>Esercizio 3.</b> τ = R C = 0,1 s; tempo di salita ≈ 2,2 τ = 0,22 s.",
    ],
)
PROGRAM = ("<h2>Corso di prova — Programma del corso</h2>"
           "<p><b>Modalità d'esame.</b> Prova scritta di due ore con esercizi numerici e una domanda di teoria, "
           "senza formulario. Chi supera lo scritto può sostenere un orale facoltativo.</p>"
           "<p><b>Argomenti.</b> Sistemi dinamici, sistemi lineari tempo-invarianti, sistemi del primo ordine, "
           "risposta al gradino, circuiti RC.</p>")


def write_exam(path, title, exercises):
    doc = fitz.open()
    html_page(doc, "<h2>%s</h2><p>Durata: 2 ore. Non è ammesso il formulario.</p>%s"
              % (title, "".join("<p>%s</p>" % e for e in exercises)))
    doc.save(str(path))


def write_folders(out):
    """Lo stesso corso organizzato in cartelle, come lo prepara uno studente."""
    for sub in ("slide", "trascrizioni", "esami", "altro"):
        (out / sub).mkdir(parents=True, exist_ok=True)
    for (name, pages), new in zip(SLIDES.items(), ("01_sistemi_dinamici.pdf", "02_primo_ordine.pdf")):
        doc = fitz.open()
        for html in pages:
            diagram_page(doc) if html is None else html_page(doc, html)
        doc.save(str(out / "slide" / new))
    for k, (title, lines) in enumerate(LESSONS, 1):
        paragraphs = [title] + ["[%02d:%02d:%02d] %s" % ((40 + i * 260) // 3600, (40 + i * 260) % 3600 // 60,
                                                        (40 + i * 260) % 60, line) for i, line in enumerate(lines)]
        if k == 1:
            (out / "trascrizioni" / "lezione01.txt").write_text("\n\n".join(paragraphs) + "\n", encoding="utf-8")
        else:
            write_docx(out / "trascrizioni" / "lezione02.docx", paragraphs)
    (out / "trascrizioni" / "lezione03.m4a").write_bytes(b"\x00\x00\x00\x18ftypM4A ")  # registrazione da trascrivere
    (title1, ex1), (title2, ex2) = EXAMS.values()
    write_exam(out / "esami" / "appello_giugno_2025.pdf", title1, ex1)
    write_exam(out / "esami" / "appello_giugno_2025_soluzioni.pdf", *SOLUTIONS)
    write_exam(out / "esami" / "esame 10-09-2025.pdf", title2, ex2)
    doc = fitz.open()
    html_page(doc, PROGRAM)
    doc.save(str(out / "altro" / "programma.pdf"))
    (out / "note_varie.txt").write_text("Ricordarsi di stampare le slide.\n", encoding="utf-8")


def main():
    args = sys.argv[1:]
    if args[:1] == ["--pptx"] and len(args) == 2:
        write_pptx(Path(args[1]))
        print("Presentazione di prova scritta in %s" % args[1])
        return
    folders = "--cartelle" in args
    args = [a for a in args if a != "--cartelle"]
    if len(args) != 1:
        sys.exit(__doc__)
    out = Path(args[0])
    out.mkdir(parents=True, exist_ok=True)
    if folders:
        write_folders(out)
        print("Corso di prova a cartelle scritto in %s" % out)
        return
    for name, pages in SLIDES.items():
        doc = fitz.open()
        for html in pages:
            diagram_page(doc) if html is None else html_page(doc, html)
        doc.save(str(out / name))
    paragraphs = []
    for title, lines in LESSONS:
        paragraphs.append(title)
        for k, line in enumerate(lines):
            sec = 40 + k * 260
            paragraphs.append("[%02d:%02d:%02d] %s" % (sec // 3600, sec % 3600 // 60, sec % 60, line))
    write_docx(out / "trascrizioni_lezioni.docx", paragraphs)
    # la stessa trascrizione in testo semplice, per la prova senza esecuzione di codice
    (out / "trascrizioni_lezioni.txt").write_text("\n\n".join(paragraphs) + "\n", encoding="utf-8")
    for name, (title, exercises) in EXAMS.items():
        doc = fitz.open()
        html_page(doc, "<h2>%s</h2><p>Durata: 2 ore. Non è ammesso il formulario.</p>%s"
                  % (title, "".join("<p>%s</p>" % e for e in exercises)))
        doc.save(str(out / name))
    print("Corso di prova scritto in %s: %s" % (out, ", ".join(sorted(p.name for p in out.iterdir()))))


if __name__ == "__main__":
    main()
