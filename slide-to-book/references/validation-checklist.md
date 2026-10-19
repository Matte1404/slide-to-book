# Validazione

Lo scopo è garantire due promesse della dispensa: che contenga tutto e che ogni rimando sia vero. Alcuni controlli li fa uno script, altri richiedono di leggere.

## 1. Controllo automatico

```bash
python3 <skill>/scripts/check_coverage.py \
    --fonti dispensa/_fonti \
    --libro dispensa/capitoli \
    --esercizi dispensa/esercizi.md \
    --copertura dispensa/copertura.md \
    --tag-report dispensa/punti-da-verificare.md
```

Se consegni solo una parte del corso, aggiungi `--solo` con gli ID delle fonti di quella parte, separati da virgola, per esempio `--solo S01,S02,S03,T01,T02,T03,E2024-02`: le fonti delle parti non ancora scritte non contano come errori, gli esercizi del catalogo vengono controllati solo per quelle fonti, e la tabella di copertura contiene solo quelle. Il confronto è per prefisso (`S1` include anche S10–S19); un valore che non corrisponde a nessun ID è un errore. Controlla che nella sezione COPERTURA dell'output compaiano esattamente le fonti che ti aspetti.

Lancialo anche durante la scrittura, dopo ogni capitolo: trova subito citazioni sbagliate o malformate, quando correggerle costa poco.

**Errori** (lo script esce con codice 1):
- slide mai citate nella dispensa;
- citazioni a ID inesistenti o a posizioni che non esistono (slide oltre l'ultima, minuto oltre la fine della lezione, formato non riconosciuto, testo dentro le parentesi);
- esercizi del catalogo `esercizi.md` che non compaiono in nessun capitolo;
- esami mai citati.

**Avvisi** (da valutare caso per caso):
- slide coperte solo da citazioni a più di 4 slide distinte, come `[S01, slide 1-45]`: lo script le conta come coperte, ma una citazione così non dice se ognuna è spiegata. Le citazioni nella stessa parentesi o in parentesi attaccate (`[S01, slide 1-4]; [S01, slide 5-8]`) contano insieme; i passi di un'animazione Beamer (pagine che ripetono la precedente aggiungendo righe) contano come una slide sola; le citazioni nella sezione "Slide di servizio" non contano come intervalli ampi;
- più di 3 slide con del testo, e più di un quarto del file, coperte solo dalla sezione "Slide di servizio". Titoli brevi, "Domande?", "Grazie" e divisori di sezione hanno poco testo e non contano, e nemmeno gli indici ripetuti a ogni sezione;
- paragrafi che affermano che qualcosa è stato detto a lezione o è uscito all'esame senza citare una fonte `T`, `E` o `X`;
- segmenti delle trascrizioni mai citati. Spesso è logistica, ma controlla di non aver perso una spiegazione o un esempio;
- esercizi citati nel libro (`[E2024-02, es. 3]`) che non sono nel catalogo `esercizi.md`: il numero può essere sbagliato, perché lo script non legge il testo dell'esame.

Con `--copertura` scrive la tabella slide → sezione che spiega la slide (le sezioni di riepilogo come "Errori comuni" compaiono solo se la slide non è spiegata altrove). Con `--tag-report` scrive l'appendice dei punti da verificare, raggruppati per tipo e con la sezione in cui compaiono.

E poi:

```bash
python3 <skill>/scripts/visual.py todo --fonti dispensa/_fonti
```

deve rispondere che non ci sono slide segnalate senza lettura visiva. Per una slide segnalata che non c'è niente da leggere (slide nascosta, immagine decorativa), aggiungi comunque una nota, per esempio `visual.py note ... "immagine decorativa, nessun contenuto"`, così esce dall'elenco.

## 2. Correzione

- **Slide coperte solo da intervalli ampi**: apri quelle slide in `_fonti/` e verifica che ogni punto sia spiegato. Poi sostituisci l'intervallo con citazioni vicine al testo che spiega ciascuna slide (`[S01, slide 14]`, `[S01, slide 15-16]`). Non spezzare l'intervallo solo per far sparire l'avviso.
- **Slide non citata**: non aggiungere una citazione solo per far passare il controllo. Apri la slide in `_fonti/`, verifica se il suo contenuto è davvero spiegato. Se non lo è, scrivilo nella sezione giusta. Se è una slide di servizio, aggiungila all'elenco delle slide di servizio nelle appendici.
- **Citazione sbagliata**: trova la posizione giusta nelle intestazioni di `_fonti/` e correggila. Se la fonte non dice quella cosa, la frase va riscritta o marcata.
- **Citazione malformata**: dentro le parentesi solo ID e posizione; i commenti vanno fuori.
- **Esercizio mancante**: aggiungi il blocco esercizio nel capitolo indicato dal catalogo.
- **Avviso su "detto a lezione" senza fonte**: aggiungi la citazione oppure riformula.

Riesegui lo script finché non ci sono più errori.

## 3. Controlli di lettura

Lo script verifica che le slide siano citate, non che siano spiegate bene. Controlla a mano:

- [ ] **Campione di completezza**: scegli 3 slide dense a caso e verifica che la dispensa spieghi tutto il loro contenuto (ogni punto, formula, dato), non solo che le citi. Fai lo stesso con 2 segmenti di trascrizione che contengono spiegazioni. Se trovi omissioni, controlla l'intero capitolo.
- [ ] Ogni sezione ⭐⭐ o ⭐⭐⭐ ha la riga "Perché" con citazioni, coerente con `importance-rules.md`.
- [ ] Ogni blocco esercizio ha "Dove l'hai visto" con file, data e numero, e lo stato della soluzione.
- [ ] Le soluzioni scritte da te sono marcate `[SOLUZIONE GENERATA]` e, se puoi eseguire codice, verificate.
- [ ] Ogni formula ha i simboli spiegati.
- [ ] Le domande di autoverifica hanno la forma della modalità d'esame; le domande del docente presenti nelle slide hanno tutte una risposta modello.
- [ ] L'introduzione contiene legenda, informazioni sull'esame e fonti disponibili.
- [ ] Le intestazioni "Fonti" dei capitoli sono in testo semplice, senza parentesi quadre.

Se correggi qualcosa, riesegui il controllo automatico.

## 4. Compilazione e consegna

Unisci e compila con `merge_book.py` (comando in SKILL.md, fase 5). Lo script controlla che ogni capitolo compaia come titolo di primo livello e, per il PDF, sceglie i font e disegna stelle e simboli con un font di simboli. Poi **guarda il risultato**, per esempio con `python3 <skill>/scripts/visual.py render --pdf dispensa/Nome-del-corso.pdf --pagine 1-2,10,20 --out controllo-pdf.png` (le pagine oltre la fine vengono ignorate):
- [ ] l'indice contiene tutti i capitoli;
- [ ] gli elenchi sono elenchi, non paragrafi con trattini;
- [ ] tabelle, formule e alberi disegnati nel codice si leggono;
- [ ] nessun carattere mancante: lo script scrive `⚠ pdf` invece di `✓ pdf` se ne mancano;
- [ ] le stelle si vedono anche nei titoli in grassetto.

Nel messaggio finale riporta:
- numero di capitoli e copertura delle slide (es. "312/312 slide");
- esercizi d'esame integrati, per tipo;
- numero di `[DA VERIFICARE]`, `[DISCREPANZA]` e `[SOLUZIONE GENERATA]`, cioè i punti da controllare con il docente o con i compagni;
- le scelte fatte senza chiedere (dalle "Scelte fatte" di `mappa.md`) e i file audio o video ancora da trascrivere;
- dove si trovano i file.
