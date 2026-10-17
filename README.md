# slide-to-book

Una skill per Claude (e per altri assistenti) che trasforma il materiale di un corso universitario in una **dispensa completa in stile libro**, orientata all'esame:

- **completa come le slide**: ogni slide è spiegata, e un controllo automatico verifica che nessuna manchi;
- **spiegata come a lezione**: usa le trascrizioni per riportare spiegazioni, esempi ed enfasi del docente;
- **orientata all'esame**: priorità ⭐/⭐⭐/⭐⭐⭐ ricavate da ciò che il docente ha sottolineato e da ciò che è uscito negli appelli passati, esercizi d'esame svolti, domande di autoverifica nella forma dell'esame (scritto, orale, quiz, progetto);
- **verificabile**: ogni affermazione ha una citazione come `[S03, slide 14]`, `[T05, 00:42:10]` o `[E2024-02, es. 1]`, così sai sempre dove l'hai visto.

## Il modo migliore per usarla

**Con Claude, mettendo il materiale del corso in cartelle.** La skill riconosce le cartelle, assegna da sola gli identificativi delle fonti e fa corrispondere slide e trascrizioni della stessa lezione.

```
mio-corso/
├── slide/          un PDF o PPTX per lezione: 01_introduzione.pdf, 02_modelli.pdf, ...
├── trascrizioni/   una trascrizione per lezione (lezione01.txt, lezione02.docx, ...)
│                   oppure un unico file con tutte le lezioni
├── esami/          appelli passati con la data nel nome: appello_giugno_2025.pdf, 2024-02-15.pdf
│                   soluzioni con "soluzioni" nel nome: appello_giugno_2025_soluzioni.pdf
└── altro/          programma del corso, esercitazioni, formulari (facoltativo)
```

- **Solo le slide sono obbligatorie.** Senza trascrizioni ed esami la dispensa è comunque completa, ma non può dirti che cosa conta di più per l'esame.
- **Numeri nei nomi dei file**: `01_…` nelle slide e `lezione01…` nelle trascrizioni fanno corrispondere la stessa lezione. Senza numeri vale l'ordine alfabetico.
- **Data nel nome degli esami**: serve a identificare l'appello e a dare più peso a quelli recenti. Vanno bene `2025-06-16`, `16-06-2025`, `giugno_2025`, `giu25`.
- **Moduli**: le sottocartelle per modulo dentro `slide/` (`slide/modulo1/`, `slide/modulo2/`) vanno bene. Se i numeri delle lezioni ripartono in ogni modulo, le slide diventano `S1-01`, `S2-01`, ...; in quel caso metti anche le trascrizioni in sottocartelle con gli stessi nomi, altrimenti non corrispondono.
- **Registrazioni audio o video**: vanno trascritte prima, per esempio con la trascrizione automatica di Teams o con Whisper. La skill legge testo (TXT, DOCX, SRT, VTT, PDF), non audio, e segnala i file da trascrivere.
- **Formati**: slide in PDF o PPTX; trascrizioni in TXT, DOCX, SRT, VTT o PDF; esami in PDF, DOCX o immagini.

Poi chiedi, per esempio:

> Usa slide-to-book su questo corso: fammi la dispensa per lo scritto.

Dove:

- **Claude Code** (consigliato per un corso intero): apri la cartella del corso (`cd mio-corso && claude`) e scrivi la richiesta. La dispensa viene salvata in `dispensa/` dentro la cartella, e il lavoro si riprende in qualsiasi momento.
- **claude.ai o app Claude, anche dal telefono**: comprimi la cartella del corso in uno zip e allegalo alla chat, oppure allega direttamente i file. La dispensa arriva come DOCX da scaricare, e come PDF se l'ambiente può compilarlo, con un archivio del lavoro per riprendere in una chat nuova. Se lo zip è troppo grande, manda un modulo alla volta.
- **Altri assistenti**: vedi [Altri assistenti](#altri-assistenti); allega i file in chat.

## Che cosa fa

La skill lavora senza fermarsi a chiedere conferme:

1. registra le fonti, dividendo per lezione anche un file unico di trascrizioni, e prepara la mappa dei capitoli;
2. analizza lezioni ed esami e assegna le priorità;
3. scrive i capitoli, salvando ogni pochi capitoli la dispensa fin lì e un archivio del lavoro;
4. controlla copertura e citazioni e consegna PDF, DOCX e Markdown, con l'elenco delle scelte fatte da sola e dei punti da verificare.

Se il corso non sta in una risposta, si ferma con "scrivi *continua*". Per rivedere le tappe scrivi "prima fammi vedere la mappa" o "un capitolo alla volta": la skill si ferma dopo la mappa e dopo il primo capitolo.

## Installazione

### claude.ai e app Claude

1. Scarica **[slide-to-book.zip](https://github.com/Matte1404/slide-to-book/releases/latest/download/slide-to-book.zip)** dall'ultima release. Non usare il pulsante *Code → Download ZIP* di GitHub: scarica tutto il repository, mentre Claude vuole uno zip che contenga solo la cartella `slide-to-book/`.
2. Attiva l'esecuzione di codice: **Settings → Capabilities → Code execution and file creation**.
3. Carica la skill: **Customize → Skills**, pulsante **+**, poi **+ Create skill → Upload a skill**, e scegli lo zip.
4. Controlla che la skill risulti attiva in **Customize → Skills**.

Sui piani Team ed Enterprise l'esecuzione di codice e le skill le abilita prima un amministratore, in **Organization settings → Plugins & skills**, scheda **Policy**. Le skill caricate su claude.ai sono personali: ognuno carica la propria copia, e non si sincronizzano con Claude Code o con l'API. Sui piani Team ed Enterprise si possono anche condividere (Customize → Skills → ⋯ → Share).

### Claude Code

```text
/plugin install slide-to-book --marketplace Matte1404/slide-to-book
```

Con versioni di Claude Code precedenti alla 2.1.275:

```text
/plugin marketplace add Matte1404/slide-to-book
/plugin install slide-to-book@slide-to-book
```

In alternativa, clona il repository (`git clone https://github.com/Matte1404/slide-to-book`) e copia la cartella a mano: `cp -r slide-to-book/slide-to-book ~/.claude/skills/`.

### Altri assistenti

Carica `slide-to-book/SKILL.md` come file insieme alla cartella `references/`, oppure incolla il suo contenuto come primo messaggio: circa 30 KB non entrano nei campi "istruzioni" di molti assistenti. Se l'assistente può eseguire Python, carica anche `scripts/`. Senza esecuzione di codice la skill lavora in modalità "Solo chat": stesso metodo, con il controllo di copertura fatto a mano.

## Requisiti

Su claude.ai non serve installare niente. Altrove gli script usano ciò che trovano e, se manca qualcosa, lo dicono:

- **Python 3.8 o successivo**, per gli script;
- per leggere i **PDF**, uno fra `pdftotext` (poppler), PyMuPDF, pypdf, pdfplumber;
- per avere la dispensa in **DOCX o HTML**, `pandoc`; per il **PDF**, anche un motore LaTeX Unicode (xelatex, lualatex o tectonic);
- PPTX, DOCX e testo non richiedono nulla.

## Struttura del repository

```
slide-to-book/                  la skill (è il contenuto dello zip)
├── SKILL.md                    istruzioni
├── references/                 regole dettagliate, lette fase per fase
│   ├── source-registry.md      ID delle fonti, cartelle del corso, estrazione, lettura visiva
│   ├── exam-modes.md           enfasi per modalità d'esame
│   ├── importance-rules.md     segnali di importanza e stelle
│   ├── chapter-template.md     modelli di introduzione, capitolo, esercizio, appendici
│   └── validation-checklist.md controllo finale
└── scripts/
    ├── extract_sources.py      riconosce le cartelle, estrae e numera le fonti
    ├── visual.py               slide da guardare: elenco, provino, annotazioni
    ├── check_coverage.py       copertura delle slide, citazioni, tag
    └── merge_book.py           unisce i capitoli e converte in PDF, DOCX o HTML
evals/                          corsi di prova e test (non fanno parte della skill)
.claude-plugin/marketplace.json installazione da Claude Code
.github/workflows/              controllo a ogni push, zip a ogni release
```

## Sviluppo

Prima di pubblicare una modifica:

```bash
pip install pyyaml pymupdf
python3 evals/smoke_test.py
```

Il test controlla che il frontmatter di `SKILL.md` sia accettato da claude.ai e fa girare gli script su due piccoli corsi di prova generati da `evals/make_fixtures.py`: file sparsi come in chat, e una cartella del corso. La stessa verifica gira su GitHub a ogni push. In `evals/evals.json` ci sono i casi d'uso completi, da far eseguire a Claude con la skill-creator di Anthropic.

Per pubblicare una nuova versione:

```bash
git tag v1.0.0
git push origin v1.0.0
```

La GitHub Action crea la release e allega `slide-to-book.zip`. Per crearlo a mano: `zip -r slide-to-book.zip slide-to-book -x '*.DS_Store' '*__pycache__*'`.

## Materiale dei corsi

Non aggiungere a questo repository slide, trascrizioni, esami o dispense: sono materiale dei docenti, e le trascrizioni possono contenere dati personali. Il `.gitignore` esclude gli zip, le cartelle `dispensa/` e `_fonti/` e i formati del materiale (PDF, PPTX, DOCX, audio e video).

Se la cartella del tuo corso è a sua volta un repository git, ricorda che `dispensa/` contiene anche il testo completo estratto dalle slide (`dispensa/_fonti/`): non pubblicarla.

## Licenza

[MIT](LICENSE)
