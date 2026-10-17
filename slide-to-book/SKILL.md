---
name: slide-to-book
description: Trasforma il materiale di un corso universitario (slide PDF/PPTX, trascrizioni o sbobinature delle lezioni, anche tutte in un unico file, esami passati) in una dispensa completa in stile libro di testo, orientata all'esame, con citazioni verificabili a slide, minuto di lezione ed esercizio d'esame. Adatta l'enfasi alla modalità d'esame (scritto, orale, quiz, progetto) e mette in evidenza ciò che il docente ha sottolineato e ciò che è uscito negli appelli. Usala ogni volta che l'utente allega slide o trascrizioni di un corso, o indica una cartella con slide/ e trascrizioni/, e chiede un riassunto, una dispensa, appunti completi o materiale per lo scritto o l'orale, anche con una sola frase come "fammi il riassunto", anche se tutto il corso sta in un PDF e anche se non dice dispensa (study guide, lecture notes, course summary, exam prep). Non usarla per riassumere in poche righe un documento che non è materiale di un corso, per fare solo flashcard o per una domanda su una slide.
license: MIT
compatibility: Funziona in qualsiasi chat. Con esecuzione di codice usa Python 3.8+ e, se ci sono, poppler o PyMuPDF per i PDF, pandoc per il DOCX e LaTeX o LibreOffice per il PDF; nessun pacchetto è obbligatorio.
---

# Slide to Book

Trasforma il materiale di un corso (slide, trascrizioni delle lezioni, esami passati) in una **dispensa in stile libro**: completa come le slide, spiegata come a lezione, orientata all'esame, con ogni affermazione rintracciabile nella sua fonte.

## Perché lavora così

Lo studente userà la dispensa **al posto** delle slide. Da qui vengono tutte le regole:

- **Non è un riassunto.** Un concetto omesso è un concetto che lo studente non studierà. Espandere e chiarire va bene, tagliare no. Se si "riassume" un corso intero in un colpo solo, il testo si comprime e perde dettagli: per questo si scrive un capitolo alla volta, rileggendo ogni volta le fonti di quel capitolo.
- **L'importanza viene dalle fonti, non dall'intuito.** Ciò su cui il docente ha insistito a lezione e ciò che è uscito agli esami pesa di più. Va reso ben visibile, senza eliminare il resto.
- **Ogni rimando deve essere verificabile.** Lo studente deve poter leggere "appello di giugno 2023, file `giugno23.pdf`, es. 2b" e aprire quel file. Una citazione inventata è peggio di nessuna citazione: per questo ogni fonte riceve un ID e uno script controlla le citazioni.

Quando l'utente chiede un "riassunto" con questa skill intende questa dispensa, non una sintesi breve.

**Se il contesto della conversazione è stato compattato** (non ricordi il formato delle citazioni, i tag o le fasi), rileggi per intero questo SKILL.md prima di continuare: dopo una compattazione ne resta solo l'inizio.

## Regole della dispensa

Valgono in ogni fase e in ogni situazione. Se a metà lavoro non le ricordi con precisione (per esempio dopo che il contesto della conversazione è stato compattato), rileggi questo file prima di scrivere il capitolo successivo: sono ciò che rende la dispensa affidabile.

### Fedeltà e tag

Il contenuto viene dalle fonti. Puoi aggiungere un passaggio intermedio, una definizione mancante o un esempio, se rende la spiegazione comprensibile, ma va marcato: lo studente deve sapere cosa ha detto il docente e cosa no. Integra solo ciò che serve a capire le slide o a risolvere gli esercizi d'esame: con slide scarne è facile che le aggiunte superino le fonti, e lo studente finisce a studiare ciò che il docente non ha detto. Marca ogni aggiunta una volta sola, all'inizio del paragrafo o del blocco, non frase per frase.

| Tag | Quando usarlo |
|---|---|
| `[INTEGRAZIONE]` | contenuto non presente nelle fonti, aggiunto per chiarezza |
| `[DA VERIFICARE]` | testo illeggibile, formula incerta, passaggio ambiguo: non tirare a indovinare |
| `[DISCREPANZA]` | le fonti si contraddicono: riporta entrambe le versioni con citazione |
| `[FUORI SLIDE]` | argomento spiegato a lezione o chiesto all'esame ma assente dalle slide |
| `[SOLUZIONE GENERATA]` | soluzione scritta da te, né ufficiale né svolta a lezione |
| `[ESCLUSO DAL DOCENTE]` | il docente ha detto che non è in programma: includi comunque ciò che le fonti ne dicono, segnalato; non scrivere tu la parte esclusa se nelle fonti non c'è |

- Per le spiegazioni privilegia la trascrizione (è come il docente l'ha spiegato), per terminologia, notazione e ordine privilegia le slide. Se c'è una contraddizione vera (un valore o una definizione diversa), usa `[DISCREPANZA]`.
- Non scrivere mai "detto a lezione" o "uscito all'esame" senza citazione: sono proprio le affermazioni su cui lo studente decide cosa studiare.
- Tralascia battute, logistica e divagazioni, salvo quando riguardano l'esame.

### Citazioni

Formato: `[ID, posizione]`. Più fonti nella stessa parentesi si separano con `;`.

- slide: `[S01, slide 14]`, `[S01, slide 12-15]`
- lezione: `[T03, 00:42:10]` (sempre ore:minuti:secondi, come nelle intestazioni) oppure `[T03, par. 27]`
- esame: `[E2023-06, es. 2b]`, oppure `[E2023-06, pag. 3]` se l'esercizio non è numerato
- altro: `[X01, pag. 4]`

Usa esattamente le posizioni che compaiono nelle intestazioni dei file in `_fonti/`: lo script verifica che ogni slide, pagina, paragrafo o minuto citato esista. Il numero di un esercizio (`es. 2b`) non può verificarlo: controllalo tu sul testo dell'esame. Dentro le parentesi vanno solo ID e posizione: un commento come `[S01, slide 3 per i primi due]` non è una citazione valida, scrivilo fuori. Metti la citazione alla fine della frase o del paragrafo che sostiene, non in fondo al capitolo: serve anche a ritrovare la slide originale mentre si studia. Per gli esercizi scrivi anche, per esteso, nome del file e data dell'appello (formato in `references/chapter-template.md`), perché è quello che lo studente vuole aprire.

### Stile

- Prima l'intuizione, poi la definizione formale, poi un esempio.
- Definisci ogni termine tecnico alla prima occorrenza e usa sempre lo stesso termine: alternare sinonimi fa pensare che siano cose diverse.
- Formule in LaTeX (`$...$`, `$$...$$`), seguite dal significato di ogni simbolo e dalle unità di misura.
- Tabelle per i confronti, elenchi numerati per le procedure.
- La lunghezza la decide il contenuto: ogni slide con contenuto sostanziale riceve almeno un paragrafo di spiegazione, e una slide densa può richiederne molti. Non accorciare per brevità.
- Mantieni i termini tecnici nella forma usata dal docente (anche in inglese, se li usa così).
- **Codice nelle slide**: se le slide lasciano al lettore il risultato di un programma o di una domanda sul codice, ricavalo e scrivilo. Se puoi eseguire quel linguaggio, verificalo eseguendo il codice; altrimenti traccia l'esecuzione a mano e marca la risposta `[SOLUZIONE GENERATA]`. L'estrazione dai PDF perde l'indentazione: ricostruiscila quando riporti il codice.
- Se la dispensa è in un'altra lingua, lascia in italiano i tag e i titoli fissi del modello di capitolo, perché lo script di controllo li riconosce così, e spiegali nella legenda.

## Ritmo di lavoro

**Di regola genera tutto senza fermarti.** Chi allega i file con una frase sola ("usa questa skill e fammi il riassunto") vuole la dispensa finita, da rivedere alla fine. Deduci dai file tutto ciò che puoi (tipi, lezioni, date, modalità d'esame). Quando qualcosa è incerto, fai la scelta più ragionevole, annotala tra le "Scelte fatte" di `mappa.md` e riassumila nel messaggio di consegna: così l'utente sa che cosa controllare senza dover rispondere a domande prima di aver visto qualcosa.

Fermati a chiedere solo se senza risposta il lavoro sarebbe inutile: i file non si aprono, non si capisce di che corso si tratta, gli allegati sembrano di corsi diversi. Anche allora, una sola domanda in un solo messaggio.

Se l'utente vuole rivedere le tappe ("prima fammi vedere la mappa", "un capitolo alla volta"), mostra registro e mappa in un unico messaggio e aspetta; poi il primo capitolo, e aspetta di nuovo. In una chat con i file, "mostrare" un capitolo vuol dire metterlo nella cartella di output e riassumere in chat, in pochi punti, che cosa contiene e che scelte di tono e lunghezza hai fatto: un capitolo intero incollato in chat non si legge sul telefono.

**Quando spezzare.** Se lavori con i file, prosegui fino alla fine del corso. Ogni pochi capitoli copia nella cartella di output la dispensa unita fin lì (`merge_book.py` senza `--extra`) e uno zip di `dispensa/`: se la risposta si interrompe o l'ambiente della chat viene azzerato, con quello zip (più le fonti) l'utente riprende in una chat nuova. Spezza la risposta solo quando non puoi continuare (conversazione molto lunga, risposta che rischia di interrompersi): consegna ciò che è pronto e chiudi con "scrivi *continua* per riprendere dal capitolo N", senza altre domande.

**Corsi lunghi.** Un corso intero può superare il migliaio di slide. Va bene consegnare per parti (per esempio un modulo alla volta): controlla e compila solo la parte finita con `--solo` (fase 5), e riparti dalla mappa per la parte successiva.

## Dove stai lavorando

La skill funziona dal terminale come da una chat sul telefono, con Claude o con un altro assistente. Capisci subito in che situazione sei: cambia il modo di lavorare, non il metodo.

| Situazione | Come riconoscerla | Come lavori |
|---|---|---|
| **Puoi eseguire codice** (Claude Code, app Claude con esecuzione di codice, altri agenti) | hai un terminale o uno strumento che esegue `python3` | cartella di lavoro e script, come descritto sotto |
| **Chat senza esecuzione di codice** | vedi gli allegati nella conversazione ma non puoi eseguire comandi | stesso metodo, in chat: sezione "Solo chat" |
| **Hai solo questo testo** (incollato in un altro assistente) | non puoi leggere i file `references/` | sezione "Solo chat", con le regole essenziali riassunte lì |

Se puoi eseguire codice:
- `<skill>`, nei comandi di questo file e dei `references/`, è la cartella di questa skill: `${CLAUDE_SKILL_DIR}`. Se al posto di un percorso vedi un segnaposto che inizia con il simbolo del dollaro, la cartella è quella da cui hai letto questo SKILL.md (su claude.ai di solito sta sotto `/mnt/skills/`). Scrivi il percorso assoluto per esteso in ogni comando: una variabile della shell non sopravvive da un comando all'altro.
- Gli allegati della chat sono su disco, in una cartella di upload (su claude.ai di solito `/mnt/user-data/uploads`). Elencala prima di iniziare: nomi e ordine dei file servono per il registro. Uno zip di solito è la cartella del corso compressa: estrailo nella cartella di lavoro e trattalo come una cartella del corso (fase 0). Se invece contiene `mappa.md` e `registro.md`, è un lavoro da riprendere (vedi "Cartella di lavoro").
- Lavora nella cartella di lavoro, mai dentro quella degli allegati, che può essere di sola lettura. A ogni consegna copia i file finali nella cartella di output della piattaforma, se c'è (su claude.ai di solito `/mnt/user-data/outputs`): è da lì che l'utente li scarica, anche dal telefono.
- Non contare su internet per installare pacchetti. Gli script usano ciò che trovano (per i PDF: pdftotext, PyMuPDF, pypdf o pdfplumber) e, se manca qualcosa, lo dicono. Se nessun estrattore PDF funziona, leggi i PDF direttamente come in "Solo chat", e prosegui.
- Se le pagine dei PDF allegati sono già visibili nella conversazione, usale per la lettura visiva invece di renderizzarle.

## Input

| Input | Obbligatorio | A cosa serve |
|---|---|---|
| Slide (PDF, PPTX) | sì | contenuto, terminologia, ordine degli argomenti |
| Trascrizioni delle lezioni (TXT, DOCX, SRT, VTT, PDF), un file per lezione o tutte in un file | no | spiegazioni, esempi ed enfasi del docente |
| Esami passati, con o senza soluzioni | no | cosa viene chiesto davvero e con che frequenza |
| Programma o scheda del corso | no | spesso dichiara la modalità d'esame |
| Altro (esercitazioni, formulari, dispense del docente) | no | esercizi svolti e materiale di supporto |

Il modo consigliato è una **cartella del corso** con le sottocartelle `slide/`, `trascrizioni/`, `esami/` e, se serve, `altro/`: lo script assegna da solo gli ID e fa corrispondere slide e trascrizioni della stessa lezione. Va bene anche ricevere i file sparsi, allegati in chat: in quel caso li classifichi tu.

Non chiedere ciò che ha un default o si può dedurre:
- **modalità d'esame**: dal programma, dalle trascrizioni o dalla forma degli esami (vedi `references/exam-modes.md`); se non si deduce, usa una struttura mista e dichiaralo nell'introduzione;
- **formulario e calcolatrice**: se non sai se sono ammessi, indica comunque quali formule e quali valori numerici vanno memorizzati;
- **lingua**: quella dell'utente; **formato**: Markdown con formule LaTeX, compilato in PDF e DOCX.

Se mancano trascrizioni o esami, non bloccarti: la skill funziona anche solo con le slide. Dillo però all'utente (all'inizio della prima risposta e di nuovo alla consegna), con suggerimenti concreti, perché senza quelle fonti la dispensa non può segnare le priorità: testi d'esame delle edizioni precedenti (anche con un altro nome del corso), liste di possibili domande pubblicate dai docenti, appunti di chi ha già sostenuto l'esame. Cerca anche nelle slide eventuali domande di autoverifica scritte dal docente (per esempio sezioni "Check your understanding"): sono un segnale utile (vedi `references/importance-rules.md`).

## Cartella di lavoro

Lavora su file, non solo in chat. Un corso intero non sta nel contesto, e i file permettono di riprendere il lavoro in un'altra sessione.

```
dispensa/
├── _fonti/          testo estratto e numerato, un file per fonte + _indice.json
├── _note/           note di analisi per ogni lezione (T03.md, ...)
├── elenco.txt       elenco ID=FILE preparato da extract_sources.py --corso
├── registro.md      registro delle fonti
├── mappa.md         capitoli → fonti, priorità, stato di avanzamento, scelte fatte
├── esercizi.md      catalogo degli esercizi (esami, lezioni, esercitazioni)
├── capitoli/        00-introduzione.md, 01-<titolo>.md, ..., 90-verso-lo-scritto.md, 99-appendici.md
├── copertura.md            generata dallo script di controllo
├── punti-da-verificare.md  generata dallo script di controllo
└── Nome-del-corso.md   la dispensa unita (più .pdf e .docx)
```

Metti `dispensa/` dentro la cartella del corso se è scrivibile (in Claude Code di solito sì: lo script la ignora quando scandisce il corso), altrimenti nella cartella di lavoro; mai dentro la cartella degli allegati di una chat. Lancia i comandi dalla cartella che contiene `dispensa/`.

**Se `dispensa/mappa.md` esiste già, o se l'utente allega un archivio di `dispensa/` o la sua `mappa.md`, stai riprendendo un lavoro.** Leggi `registro.md` e `mappa.md` e riparti dal primo capitolo non completato, senza rifare le fasi già chiuse. In una chat nuova le fonti vanno riallegate: gli ID restano quelli del registro.

## Procedura

Se non puoi leggere i file `references/` citati nelle fasi, usa le regole essenziali in fondo alla sezione "Solo chat".

Tieni traccia delle fasi (con la lista dei task, se c'è) e di' all'utente a che punto sei: Fase 0 registro · Fase 1 mappa · Fase 2 analisi di lezioni ed esami · Fase 3 priorità · Fase 4 scrittura · Fase 5 appendici e validazione.

### Fase 0: registro delle fonti

Leggi `references/source-registry.md` (ID, cartelle del corso, estrazione, slide da guardare, formato del registro), poi:

1. **Cartella del corso** (sottocartelle `slide/`, `trascrizioni/`, `esami/`, `altro/`): lascia allo script classificazione e ID, che sbaglia meno di un elenco scritto a mano. In Claude Code, dalla cartella del corso:
   ```bash
   python3 <skill>/scripts/extract_sources.py --out dispensa/_fonti --corso .
   ```
   Per uno zip estratto nella cartella di lavoro, `--corso` è la cartella estratta. Lo script scrive `dispensa/elenco.txt` ed estrae tutto. Controlla l'elenco: `S03` e `T03` devono essere la stessa lezione, le date degli esami giuste, ogni soluzione abbinata al suo esame. Lo script segnala anche i file audio o video, che vanno trascritti prima (dillo all'utente, senza fermarti), e quelli che non sa classificare: decidi tu, correggi l'elenco e rilancia con `--lista dispensa/elenco.txt`, che estrae solo ciò che manca. Rilanciare `--corso` dopo aver aggiunto file è sicuro: le fonti già estratte tengono il loro ID.
2. **File sparsi** (allegati in chat, cartella senza sottocartelle): classifica tu ogni file (slide, trascrizione, esame, altro), assegna un ID (`S01`, `T03`, `E2023-06`, `X01`) ed estrai il testo:
   ```bash
   python3 <skill>/scripts/extract_sources.py --out dispensa/_fonti \
       S01=/mnt/user-data/uploads/lez01.pdf T=/mnt/user-data/uploads/trascrizioni.docx \
       E2023-06=/mnt/user-data/uploads/giugno23.pdf
   ```
   Un unico file con le trascrizioni di più lezioni si passa con il solo prefisso, `T=file`: lo script lo divide per lezione, prende il numero dal titolo ("Lezione 3" → `T03`) e stampa come lo ha diviso. Controlla la divisione e riportala nel registro. Con molti file scrivi le coppie `ID=FILE` in un file e usa `--lista elenco.txt`.
3. In tutti e due i casi lo script stampa una tabella delle fonti e segnala le slide da guardare: l'estrazione del testo perde immagini con citazioni, schermate, diagrammi, simboli come ≠ e ∀, esponenti. Guardale con `<skill>/scripts/visual.py` (`todo`, `render`, `note`: comandi in `references/source-registry.md`) e trascrivi ciò che il testo estratto non contiene. Guarda anche le slide il cui testo ha formule chiaramente rotte.
4. Scrivi `registro.md` e ricontrolla tu tipi, date e corrispondenza tra lezioni e slide: un errore qui si propaga a tutte le citazioni. Annota i dubbi tra le "Scelte fatte" di `mappa.md`.

### Fase 1: mappa del corso

Leggi `references/exam-modes.md`, perché la modalità d'esame influenza la struttura (per esempio un capitolo dedicato ai tipi di esercizio). Poi scrivi i capitoli in `mappa.md`:

```markdown
| Cap. | Titolo | Slide | Lezioni | Esercizi | Priorità | Stato |
|---|---|---|---|---|---|---|
| 1 | Introduzione ai sistemi | S01 3–20 | T01 00:05:00–00:50:00 | — | — | da fare |
| 2 | Modelli nel dominio del tempo | S01 21–45, S02 1–12 | T01 00:50:00–fine, T02 | 4 | — | da fare |

Slide di servizio (titolo, indice, ringraziamenti): S01 1–2, S02 13

## Scelte fatte
- Modalità d'esame dedotta dagli appelli: scritto con esercizi [E2023-06, pag. 1]
```

Ogni slide sta in un capitolo, oppure nell'elenco delle slide di servizio (scrivilo subito anche in `99-appendici.md`: vedi `references/chapter-template.md`). Segui l'ordine del corso, salvo motivi forti. Con lo scritto con esercizi aggiungi il capitolo di esercitazione `90-verso-lo-scritto.md`. Le colonne Esercizi e Priorità si riempiono nelle fasi 2 e 3.

Poi prosegui (vedi "Ritmo di lavoro").

### Fase 2: analisi di lezioni ed esami

Qui scopri cosa conta. Lavora un file alla volta e scrivi i risultati su disco: così nessun esercizio va perso e il contesto resta leggero. Per riconoscere l'enfasi del docente usa `references/importance-rules.md`.

**Per ogni trascrizione**, leggila insieme alle sue slide e scrivi `_note/T03.md` con:
- l'allineamento: quali segmenti spiegano quali slide;
- spiegazioni, esempi e analogie che nelle slide non ci sono (diventeranno contenuto della dispensa);
- l'enfasi ("questo è importante", "all'esame...") e le esclusioni ("questo non lo chiedo"), con citazione;
- gli esercizi svolti a lezione;
- le informazioni sull'esame (struttura, punteggi, regole);
- gli argomenti spiegati ma assenti dalle slide, marcati `[FUORI SLIDE]`.

**Per ogni esame**, aggiungi ogni esercizio o domanda a `esercizi.md`:

```markdown
| Rif. | File | Origine | Data | Argomento | Tipo | Cap. | Soluzione |
|---|---|---|---|---|---|---|---|
| [E2023-06, es. 2b] | esami/giugno23.pdf | esame | 14/06/2023 | risposta al gradino | A | 4 | ufficiale [E2023-06-sol, pag. 2] |
| [T05, 01:10:20] | trascrizioni/lez05.txt | lezione | 12/03/2026 | risposta al gradino | A | 4 | svolta a lezione |
```

Poi raggruppa gli esercizi in **tipi** (stessa struttura, dati diversi; per le domande di teoria, stesso argomento) e conta in quanti appelli compare ogni tipo. Da qui vengono l'etichetta `RICORRENTE ×N` e la lista degli esercizi da padroneggiare. Un esercizio che non corrisponde a nessuna slide va comunque spiegato, perché è uscito all'esame: marcalo `[FUORI SLIDE]` e collocalo nel capitolo più vicino.

### Fase 3: priorità

Applica `references/importance-rules.md` a ogni concetto (sezione) e capitolo e aggiorna `mappa.md`. Ogni ⭐⭐ o ⭐⭐⭐ deve poter essere giustificato con una citazione: è un'affermazione sulle fonti, non un'opinione.

### Fase 4: scrittura

Per ogni capitolo:

1. Leggi solo ciò che serve: le slide del capitolo in `_fonti/`, le note di lezione pertinenti, i segmenti di trascrizione citati e gli esercizi del capitolo. Rileggere le fonti, invece di affidarti alla memoria, è ciò che mantiene il testo fedele e completo.
2. Scrivi `capitoli/NN-titolo.md` seguendo `references/chapter-template.md`, le "Regole della dispensa" qui sopra e l'enfasi della modalità d'esame (`references/exam-modes.md`).
3. Prima di passare oltre, scorri le slide del capitolo una per una e verifica che ognuna sia spiegata, non solo citata. Lancia `scripts/check_coverage.py` (comando in `references/validation-checklist.md`): trova subito le citazioni sbagliate, quando correggerle costa poco.
4. Aggiorna lo stato in `mappa.md`.

Dopo il **primo** capitolo rileggilo con occhio critico (lunghezza, profondità, tono, ogni slide spiegata) e fissa lì il livello per gli altri: correggere ora costa molto meno che riscrivere dieci capitoli. Mostralo all'utente prima di proseguire solo se ha chiesto di rivedere le tappe.

Scrivi anche `00-introduzione.md` (modello in `references/chapter-template.md`): come usare la dispensa, legenda di stelle, etichette, tag e citazioni, e come è fatto l'esame.

### Fase 5: appendici e validazione

Scrivi `99-appendici.md` e segui `references/validation-checklist.md`, che usa `scripts/check_coverage.py` (con `--copertura` e `--tag-report` genera le appendici di copertura e dei punti da verificare). Consegna solo quando il controllo è superato: se fallisce, correggi e riesegui.

Infine unisci e compila con `scripts/merge_book.py`, non con `cat`: un capitolo che non finisce con un a capo incollerebbe il titolo del successivo alla sua ultima riga, facendolo sparire dall'indice.
```bash
python3 <skill>/scripts/merge_book.py --capitoli dispensa/capitoli \
    --extra dispensa/punti-da-verificare.md dispensa/copertura.md \
    --out dispensa/Nome-del-corso.md --titolo "Nome del corso" --pdf --docx
```
Dai al file il nome del corso (per esempio `--out dispensa/Nome-del-corso.md`): è quello che l'utente vede tra i download. Lo script produce i formati che l'ambiente permette e dice che cosa manca: il Markdown unito c'è sempre, il DOCX con pandoc, il PDF con pandoc e LaTeX oppure, senza LaTeX, convertendo il DOCX con LibreOffice. Se nel PDF mancano caratteri scrive `⚠ pdf` invece di `✓ pdf`: guarda le pagine indicate. Sul telefono un PDF o un DOCX si legge meglio del Markdown. **Guarda alcune pagine del PDF** (indice, un capitolo con elenchi, tabelle e codice): è il modo più rapido per scoprire problemi di resa che il Markdown non mostra.

Copia nella cartella di output della piattaforma, se c'è, la dispensa compilata e lo zip di `dispensa/`. Consegna con un breve resoconto: capitoli scritti, copertura delle slide, esercizi integrati, le scelte fatte senza chiedere (da `mappa.md`), il numero di `[DA VERIFICARE]` e quante soluzioni hai scritto tu (`[SOLUZIONE GENERATA]`), cioè i punti che lo studente dovrebbe controllare.

## Solo chat

Se non puoi eseguire script o scrivere file, il metodo resta lo stesso; cambiano gli strumenti.

1. **Registro.** Assegna gli ID come sopra, seguendo nomi e ordine degli allegati. "slide N" è la N-esima pagina del file (non il numero stampato sulla slide). Se le trascrizioni di più lezioni sono in un unico file, dividile tu sui titoli di lezione, sulle date o dove i timestamp ripartono da zero. Cita le lezioni con i timestamp; se mancano, numera tu i paragrafi del file e scrivi nel registro come li hai contati, così ogni citazione resta verificabile.
2. **Niente conferme di default**: apri la prima risposta con registro, mappa e scelte fatte, poi inizia subito a scrivere (vedi "Ritmo di lavoro"). Le fasi 2 e 3 non producono file: il catalogo degli esercizi, i tipi e le priorità aprono la prima consegna di capitoli.
3. **Lettura visiva**: guarda come immagine le pagine con poco testo, i diagrammi e le formule con apici, pedici o simboli; il testo estratto li perde.
4. **Pochi capitoli per risposta**, rileggendo ogni volta le pagine e le trascrizioni del capitolo invece di affidarti a ciò che ricordi. In fondo a ogni capitolo scrivi le slide che copre (`Copertura: S01 3-20, S02 1-12`), in testo semplice. Ricalcola ogni risultato numerico in un secondo modo prima di consegnarlo: senza codice nessuno lo controlla al posto tuo.
5. **Chiudi ogni risposta con la mappa aggiornata**, in forma compatta (capitoli fatti, capitoli da fare) e, se il lavoro non è finito, con "scrivi *continua*": in chat non ci sono file, e con quella mappa e le fonti il lavoro riprende anche in una conversazione nuova.
6. **Controllo finale a mano**: confronta l'elenco delle pagine di ogni file di slide con le righe "Copertura". Ogni slide deve stare in un capitolo o tra le slide di servizio; riporta il risultato ("S01: 45/45 slide"). Poi spiega all'utente come avere un documento unico: copiare i capitoli in un file `.md`, oppure chiedere a un assistente con esecuzione di codice di compilarli in PDF o DOCX.
7. **Materiale troppo grande** per una conversazione: chiedi all'utente di mandarlo a gruppi (per esempio un modulo alla volta, con le trascrizioni di quel modulo) e lavora per parti, riprendendo dalla mappa.

Se non puoi leggere i file `references/`, queste sono le regole essenziali:
- **Stelle**: ⭐⭐⭐ se è uscito all'esame ed è stato sottolineato a lezione, oppure se il docente lo ha indicato per l'esame, oppure se è uscito in 2 o più appelli; ⭐⭐ se è uscito una volta o è stato sottolineato a lezione; ⭐ tutto il resto. Le stelle vanno a ogni sezione (un concetto); la priorità di un capitolo è quella della sua sezione più importante. Sotto ogni sezione ⭐⭐ o ⭐⭐⭐, una riga *Perché* con le citazioni, per esempio *Perché ⭐⭐⭐: uscito in 2 appelli [E2024-02, es. 1]; [E2025-01, es. 3] e sottolineato a lezione [T03, 00:42:10].* Un argomento escluso dal docente prende ⭐ e `[ESCLUSO DAL DOCENTE]`, anche se è uscito in esami vecchi; gli esami di un altro docente si includono ma non contano per stelle e ricorrenze.
- **Enfasi del docente**: "è importante", "ricordatevi", "non confondete", "all'esame lo chiedo", "esce sempre", "domanda classica"; esclusioni: "non lo chiedo", "solo per cultura", "non è in programma". Leggere la slide ad alta voce non è enfasi.
- **Etichette**: `RICORRENTE ×N` (tipo di esercizio, cioè stessa struttura con dati diversi, o stesso argomento per le domande di teoria, uscito in N appelli), `INDICATO DAL DOCENTE` (con citazione). Con le sole slide niente stelle, che sarebbero inventate: usa al loro posto `DOMANDA DEL DOCENTE` (sezione che risponde a una domanda di autoverifica scritta nelle slide) ed `EVIDENZIATO NELLE SLIDE`, e dichiara nell'introduzione che sono segnali deboli.
- **Capitolo**: intestazione con fonti (in testo semplice) e priorità; *In breve* (3–7 punti); sezioni con intuizione, definizione ed esempio, citazioni nel testo; riquadro per l'enfasi del docente (`> 🎓 **Detto a lezione** [T03, 00:42:10]: ...`); tabella delle formule con simboli e unità; esercizi; errori comuni; domande di autoverifica nella forma dell'esame; collegamenti con gli altri capitoli.
- **Esercizio**: "Dove l'hai visto" con nome del file, data dell'appello e numero dell'esercizio (`Appello del 14/06/2023, file esami/giugno23.pdf, esercizio 2b [E2023-06, es. 2b]`); testo fedele all'originale; svolgimento a passi; stato della soluzione (ufficiale, svolta a lezione o `[SOLUZIONE GENERATA]`). Per le risposte modello scritte da te basta `[SOLUZIONE GENERATA]` una volta, in testa alla sezione.
- **Modalità d'esame**: scritto con esercizi, una procedura per tipo e tutti gli esercizi svolti; domande aperte, definizioni precise e risposte modello; orale, spiegazione discorsiva e riquadri "Come lo diresti all'orale"; quiz, distinzioni sottili e domande a 4 opzioni; progetto, motivazioni, ipotesi e compromessi dei metodi. Se l'esame mescola le forme (per esempio esercizi numerici e una domanda teorica), applica a ciascuna parte le sue regole.
- **Introduzione e appendici**: legenda (stelle, etichette, tag, citazioni) e com'è fatto l'esame all'inizio; in fondo registro delle fonti, percorso rapido con le sezioni ⭐⭐⭐, mappa degli esami, glossario, indice delle formule, slide di servizio (titolo, indice, ringraziamenti) con la loro citazione, punti da verificare (tutti i tag) e il risultato del controllo di copertura.

## File di riferimento

| File | Quando leggerlo |
|---|---|
| `references/source-registry.md` | Fase 0: ID, cartelle del corso, estrazione, lettura visiva, registro |
| `references/exam-modes.md` | Fasi 1 e 4: enfasi per modalità d'esame |
| `references/importance-rules.md` | Fasi 2 e 3: segnali di importanza e stelle |
| `references/chapter-template.md` | Fase 4: introduzione, capitoli, esercizi, appendici |
| `references/validation-checklist.md` | Fasi 4 e 5: controllo automatico e controlli di lettura |

| Script | A cosa serve |
|---|---|
| `scripts/extract_sources.py` | Fase 0: classifica la cartella del corso, estrae e numera le fonti, segnala le slide da guardare |
| `scripts/visual.py` | Fase 0: elenca, mostra e annota le slide da guardare |
| `scripts/check_coverage.py` | Fasi 4 e 5: copertura, citazioni, tag, appendici generate |
| `scripts/merge_book.py` | Fase 5: unisce i capitoli e compila PDF, DOCX o HTML |
