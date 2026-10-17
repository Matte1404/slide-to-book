# Registro delle fonti

Il registro dà a ogni file un ID breve. Tutte le citazioni della dispensa usano questi ID, così "dove l'ho visto?" ha sempre una risposta precisa.

## Schema degli ID

| Prefisso | Tipo | Esempi | Regola |
|---|---|---|---|
| `S` | slide | `S01`, `S02` | un ID per file, numerati nell'ordine del corso |
| `T` | trascrizione | `T01`, `T02` | stesso numero delle slide della stessa lezione, quando possibile (`T03` ↔ `S03`) |
| `E` | esame | `E2023-06`, `E2024-02a` | anno e mese dell'appello; una lettera se ci sono più prove nello stesso mese |
| `E…-sol` | soluzioni d'esame | `E2023-06-sol` | quando le soluzioni sono in un file separato |
| `X` | altro | `X01`, `X02` | programma del corso, esercitazioni, formulari, dispense del docente |

Gli ID devono iniziare con la lettera del tipo seguita da una cifra (`S01`, non `SL1`): lo script di controllo li riconosce così.

Se un file di slide contiene più lezioni (per esempio un unico PDF con tutte le slide del corso), usa un solo ID e lascia che i capitoli lo dividano per intervalli di slide. Le trascrizioni invece vanno divise per lezione, perché i timestamp ripartono da zero a ogni lezione: un unico file di trascrizioni si passa come `T=file` e lo script lo divide (vedi sotto). Se una lezione ha più file, dai a ciascuno un ID.

## Cartella del corso

Con `--corso cartella` lo script classifica i file dalla sottocartella in cui stanno e assegna gli ID da solo:

| Sottocartella (anche con numeri davanti, es. `1_slide`) | Tipo | ID |
|---|---|---|
| `slide`, `slides`, `lucidi`, `presentazioni` | slide | `S01`, `S02`, ... |
| `trascrizioni`, `registrazioni`, `sbobinature`, `sbobine`, `transcripts`, `recordings`, `audio` | trascrizione | `T01`, `T02`, ... oppure `T=` se il file è uno solo |
| `esami`, `appelli`, `compiti`, `prove`, `exams` | esame | `E2025-06`, `E2025-06-sol`, ... |
| `altro`, `programma`, `esercitazioni`, `esercizi`, `formulari`, `materiale`, `extra` | altro | `X01`, `X02`, ... |

Regole:
- **Numeri**: se ogni file ha un numero diverso nel nome (`03_intro.pdf`, `lez03.txt`, `Lezione 3.docx`), quello diventa l'ID, così `S03` e `T03` sono la stessa lezione. Altrimenti si numera in ordine di nome. Con sottocartelle per modulo e numeri che ripartono (`slide/modulo1/01_…`, `slide/modulo2/01_…`) gli ID diventano `S1-01`, `S2-01`.
- **Esami**: la data viene dal nome del file (`2025-06-16`, `20250616`, `16-06-2025`, `giugno_2025`, `giu25`, `settembre 2024`). Due appelli nello stesso mese diventano `E2024-02a`, `E2024-02b`; senza data, `E01`, `E02` (scrivi "data sconosciuta" nel registro). Un file con "sol", "soluzioni", "correzione" o "svolto" nel nome sono le soluzioni dell'appello con la stessa data: `E2025-06-sol`.
- **Audio e video** (`.mp3`, `.m4a`, `.wav`, `.mp4`, ...): non vengono estratti. L'elenco li riporta come "da trascrivere prima": dillo all'utente nel primo messaggio e alla consegna, e prosegui con il resto.
- **File fuori dalle sottocartelle note** (anche nella cartella principale): riportati come "da classificare". Guardali e, se servono, aggiungili all'elenco con l'ID giusto.
- Le cartelle `dispensa/`, quelle nascoste e quelle che iniziano con `_` vengono ignorate.

L'elenco finisce in `dispensa/elenco.txt` (o dove dice `--elenco`), con un commento per ogni gruppo che spiega come sono stati scelti gli ID. Per correggere: modifica l'elenco, cancella da `_fonti/` i file degli ID che hai cambiato e rilancia con `--lista dispensa/elenco.txt --force`.

## Estrazione del testo

```bash
python3 <skill>/scripts/extract_sources.py --out dispensa/_fonti \
    S01=slide/01_intro.pdf S02=slide/02_modelli.pptx \
    T01=trascrizioni/lez01.txt T02=trascrizioni/lez02.vtt \
    E2023-06=esami/giugno23.pdf X01=programma.pdf
```

Con molti file, scrivi una coppia `ID=FILE` per riga in un file e passalo con `--lista elenco.txt`: passare decine di argomenti costruiti in un ciclo della shell è fragile (zsh, per esempio, non divide le variabili in parole come bash).

Cosa fa:
- **Slide (PDF/PPTX)**: una sezione per slide, con intestazione `## [S01, slide N]`. Dai PDF toglie le righe ripetute su almeno l'80% delle pagine (autore, nome del corso, anno, numero di pagina) e le annota in un commento in cima al file. Dai PPTX estrae anche le note del relatore e segnala le slide nascoste.
- **Numerazione**: "slide N" è sempre la N-esima pagina del file. Nelle slide Beamer il numero stampato nel piè di pagina conta i frame ed è più basso, perché le animazioni occupano più pagine: dillo nell'introduzione della dispensa.
- **Trascrizioni** (TXT, DOCX, MD, SRT, VTT o PDF): se trova timestamp (`[00:42:10]`, `00:42`, SRT/VTT, formato Whisper o Teams), raggruppa il testo in blocchi da circa un minuto con intestazione `## [T01, 00:42:10]`. Altrimenti divide in paragrafi numerati: `## [T01, par. 27]`.
- **Più lezioni in un file** (`T=trascrizioni.docx`, anche TXT, MD o PDF): divide il file sulle righe-titolo di lezione ("Lezione 3", "LEZIONE N. 3 - 12/03", "Lecture 3", "# Lezione del 12 marzo"); se non ce ne sono, dove i timestamp ripartono da zero. Il numero della lezione nel titolo diventa l'ID (`Lezione 3` → `T03`); senza numeri, o con numeri ripetuti, numera in ordine. Un indice delle lezioni in cima al file viene unito alla prima lezione. Lo script stampa il criterio usato e il titolo di ogni parte: controlla che le lezioni siano quelle giuste e riportale nel registro. Se la divisione è sbagliata, dividi il file a mano in un file per lezione e usa `T01=...`, `T02=...`. Più file passati con `T=` nello stesso comando vengono numerati di seguito; un ID che esiste già per un altro file è un errore, non viene sovrascritto.
- **Esami e altro (PDF)**: una sezione per pagina, `## [E2023-06, pag. 2]`. Gli esercizi li numeri tu nel catalogo `esercizi.md`, usando la numerazione dell'esame.
- **Immagini** (foto o scansioni): registrate con una nota, da leggere visivamente.
- **Markdown** (per esempio una scheda del corso): un paragrafo per sezione, a partire da ogni titolo, mantenendo le righe di tabelle ed elenchi.
- Scrive `_fonti/_indice.json`, che serve a `check_coverage.py`, e stampa una tabella riassuntiva da usare per il registro.

Per aggiungere file in un secondo momento, rilancia lo script solo con i nuovi file: l'indice si aggiorna. Lo script non sovrascrive un file già estratto, perché potresti averci aggiunto trascrizioni visive. Per rigenerarlo usa `--force`, sapendo che le aggiunte manuali andranno perse e che, se la versione dello script è cambiata, la numerazione di paragrafi e blocchi può cambiare: non rigenerare una fonte già citata nei capitoli. Per cambiare un ID, estrai di nuovo il file con il nuovo ID e cancella il vecchio file da `_fonti/` e dall'indice.

Dipendenze: per PPTX, DOCX e testo nessuna. Per i PDF basta uno fra `pdftotext` (poppler), PyMuPDF, `pypdf` e `pdfplumber`: lo script usa il primo che trova. Le slide con immagini si segnalano con `pdfimages` (poppler) o PyMuPDF; senza nessuno dei due quella segnalazione manca, e conviene scorrere le slide visivamente. Se non c'è nessun estrattore PDF e non puoi installarne uno, leggi i PDF direttamente e numera tu le pagine (vedi "Solo chat" in SKILL.md).

## Slide da guardare visivamente

L'estrazione del testo perde formule, grafici, diagrammi e testo dentro le immagini. Lo script segnala tre casi, con una riga `⚠` sotto l'intestazione della slide:
- **poco testo** (meno di 40 caratteri dopo aver tolto i piè di pagina): divisori di sezione, slide-immagine;
- **immagini di contenuto** (con `pdfimages` o PyMuPDF, escludendo loghi e sfondi ripetuti, icone e strisce decorative): citazioni dentro un'immagine, schermate, diagrammi raster. Una slide può avere molto testo e un'immagine che dice la cosa più importante;
- **molte righe cortissime**: alberi, diagrammi vettoriali, formule a più livelli, il cui testo c'è ma senza struttura.

Guardale e trascrivi il contenuto sotto l'intestazione, iniziando con `(lettura visiva)` così è chiaro da dove viene. Guarda anche le slide con formule rotte: simboli come ≠, ∀, ⟨⟩ ed esponenti spariscono spesso senza lasciare traccia (`x ≠ y` diventa `x , y`, `9^8` diventa `98`).

Come vederle, con `scripts/visual.py`:
- `python3 <skill>/scripts/visual.py todo --fonti dispensa/_fonti`: le slide segnalate che non hanno ancora una lettura visiva;
- `python3 <skill>/scripts/visual.py render --pdf file.pdf --pagine 14,16-21 --out provino.png --dpi 60`: più pagine in un'unica immagine (60 dpi bastano per le slide web con testo grande, 80–90 per le slide Beamer e le formule);
- `python3 <skill>/scripts/visual.py note --fonti dispensa/_fonti S01 14 "Diagramma: …"`: aggiunge la trascrizione al file della fonte.

`render` usa `pdftoppm` (poppler) o PyMuPDF.

Altri modi:
- **PDF allegato in chat**: se le pagine ti sono già visibili nella conversazione, guardale lì.
- **PDF**: apri le pagine come immagini (per esempio con uno strumento di lettura file che mostra le pagine PDF, oppure `pdftoppm -png -r 80 -f N -l N file.pdf out`).
- **Nessun modo di vedere le pagine**: scrivi `[DA VERIFICARE]` con il motivo, e nel messaggio di consegna elenca le slide per cui servirebbe uno screenshot.
- **PPTX**: se molte slide sono immagini, convertilo con LibreOffice se è installato (`soffice --headless --convert-to pdf file.pptx`); altrimenti scrivi nel messaggio di consegna che l'esportazione in PDF permetterebbe di leggerle. Mantieni la stessa numerazione.
- **Esami scansionati**: stessa procedura. Annota nel registro che il file è una scansione.

Se una parte resta illeggibile anche visivamente, scrivi `[DA VERIFICARE]` e descrivi cosa non si legge.

## Formato di `registro.md`

```markdown
# Registro delle fonti

| ID | File | Tipo | Lezione / appello | Data | Unità | Note |
|---|---|---|---|---|---|---|
| S01 | slide/01_intro.pdf | slide | Lezione 1: Introduzione | — | 45 slide | 3 slide lette visivamente |
| T01 | trascrizioni/lez01.txt | trascrizione | Lezione 1 | — | 92 blocchi, 00:00–01:31 | con timestamp |
| E2023-06 | esami/giugno23.pdf | esame | Appello di giugno 2023 | 2023-06-14 | 4 pag., 5 esercizi | soluzioni in E2023-06-sol |
| E2023-06-sol | esami/giugno23_sol.pdf | soluzioni | Appello di giugno 2023 | 2023-06-14 | 3 pag. | ufficiali |
| X01 | programma.pdf | programma | — | — | 3 pag. | modalità d'esame a pag. 2 |

**Disponibilità delle fonti:** trascrizioni per alcune lezioni; esami degli ultimi anni, alcuni con soluzioni.
```

La riga "Disponibilità delle fonti" serve a capire quanto sono affidabili le priorità: una lezione senza trascrizione non può fornire segnali di enfasi.

## Casi particolari

- **Trascrizioni senza timestamp**: lo script numera i paragrafi. Va bene così: le citazioni diventano `[T03, par. 27]`.
- **Data dell'esame sconosciuta**: cercala nel nome del file e nell'intestazione del testo. Se non c'è, usa l'anno se lo conosci (`E2023`, `E2023b`) o un numero progressivo (`E01`), scrivi "data sconosciuta" nel registro e trattalo come esame non recente. Non fermarti a chiederla.
- **Esami di un altro docente o di un vecchio programma**: annotalo nella colonna Note. Si includono, ma non contano per stelle e ricorrenze (vedi `importance-rules.md`).
- **Esami senza soluzioni**: le scriverai tu e le marcherai `[SOLUZIONE GENERATA]`. Se le soluzioni sono in un altro file, registralo con il suo ID e collegalo nelle Note.
- **Lezioni senza slide** (lavagna, esercitazioni a voce): la trascrizione è l'unica fonte. Collegala al capitolo più vicino e marca i contenuti `[FUORI SLIDE]`.
