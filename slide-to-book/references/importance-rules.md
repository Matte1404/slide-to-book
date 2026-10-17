# Regole di importanza

Le stelle dicono allo studente dove investire il tempo. Sono un'affermazione sulle fonti, non un giudizio personale: ogni ⭐⭐ o ⭐⭐⭐ deve poter essere giustificata con una citazione.

## I tre segnali

1. **Esame**: il concetto serve in almeno un esercizio o una domanda di un esame passato (dal catalogo `esercizi.md`).
2. **Lezione**: il docente ci si è soffermato. Lo ha spiegato oltre la lettura della slide, ha fatto esempi, ci è tornato più volte o in più lezioni, oppure lo ha sottolineato esplicitamente.
3. **Indicazione esplicita per l'esame**: il docente ha detto che lo chiederà, che è una domanda classica, che esce sempre.

Leggere la slide ad alta voce non è un segnale. Se ci sono le trascrizioni, quasi tutto è stato "detto a lezione": conta dove il docente ha speso tempo e parole. Un esempio da solo non basta, perché molti docenti ne fanno uno per slide: il segnale "lezione" richiede un'enfasi esplicita (le formule qui sotto) oppure un tempo nettamente superiore a quello delle altre slide, o un ritorno sull'argomento in un'altra lezione.

Due segnali più deboli si trovano nelle slide stesse:

4. **Domande del docente nelle slide**: domande di autoverifica scritte dal docente (sezioni "Check your understanding", "Domande di ripasso", "Self-assessment"). Spesso hanno la forma delle domande d'esame e a volte sono proprio la lista di possibili domande. Marca le sezioni che rispondono a una di queste domande con l'etichetta `DOMANDA DEL DOCENTE`, indicando numero e citazione, e raccogli le domande con risposta modello alla fine del capitolo.
5. **Enfasi dell'autore nelle slide**: punti che le slide stesse marcano come importanti (simboli `!` a inizio riga, "important", "remember", definizioni in riquadri, avvertimenti espliciti come "attenzione: errore frequente"). Usali con l'etichetta `EVIDENZIATO NELLE SLIDE`, mai come stelle: dicono che cosa l'autore ritiene centrale, non che cosa viene chiesto.

### Come riconoscere l'enfasi nelle trascrizioni

Esempi di formule tipiche, da riconoscere anche quando sono dette con altre parole:

- **Importanza**: "è importante", "è fondamentale", "attenzione", "ricordatevi", "tenete a mente", "non confondete", "questo dovete saperlo", "lo ripeto", "è un classico", "il concetto chiave è".
- **Esame**: "all'esame", "allo scritto", "all'orale", "questo lo chiedo", "esce spesso", "domanda tipica", "negli appelli passati", "è già uscito", "vi do un consiglio per l'esame".
- **Esclusione**: "questo non lo chiedo", "non è in programma", "lo saltiamo", "solo per cultura", "facoltativo", "non serve per l'esame".

Se il corso è in inglese: "this will be on the exam", "make sure you know", "this is important", "you won't be asked about this", e simili.

## Livelli

| Livello | Quando |
|---|---|
| ⭐⭐⭐ **Fondamentale** | uscito all'esame **e** sottolineato a lezione; oppure indicato esplicitamente dal docente per l'esame; oppure ricorrente in 2 o più appelli |
| ⭐⭐ **Importante** | uscito all'esame una volta, **oppure** sottolineato a lezione |
| ⭐ **Da sapere** | presente nelle slide (o solo letto a lezione) |

Etichette aggiuntive, combinabili con le stelle:
- `RICORRENTE ×N`: il tipo di esercizio o di domanda compare in N appelli distinti. Per gli esercizi il tipo è la struttura (stessi passaggi, dati diversi); per le domande di teoria è l'argomento, non la forma: "definisci X" e "definisci Y" sono due tipi diversi.
- `INDICATO DAL DOCENTE`: il docente lo ha indicato per l'esame, con citazione `[T.., posizione]`.

È invece un tag, con le regole dei tag di SKILL.md:
- `[ESCLUSO DAL DOCENTE]`: il docente lo ha escluso dal programma.

## Granularità

- Assegna le stelle a ogni **sezione** (concetto), nel titolo: `## 3.2 Risposta al gradino ⭐⭐⭐`.
- Sotto ogni sezione ⭐⭐ o ⭐⭐⭐ scrivi una riga "Perché" con le citazioni, per esempio: *Perché ⭐⭐⭐: uscito in 3 appelli [E2023-06, es. 2b]; [E2024-02, es. 1]; [E2025-01, es. 3] e sottolineato a lezione [T03, 00:42:10].* Lo studente vede il motivo e può verificarlo.
- La priorità del **capitolo** è quella della sua sezione più importante. Nell'intestazione indica anche quanti esercizi d'esame contiene, così due capitoli ⭐⭐⭐ si distinguono.

## Aggiustamenti

- **Esami recenti contano di più.** Gli ultimi 2–3 anni rappresentano meglio l'esame attuale: a parità di stelle, metti prima ciò che è uscito di recente nel percorso rapido e nella mappa degli esami. Un esame di un altro docente o di un programma diverso non conta per le stelle e per `RICORRENTE`; l'esercizio va comunque incluso, segnalando la sua origine.
- **L'indicazione attuale del docente prevale.** Se un argomento è uscito in esami vecchi ma il docente ora dice che non lo chiede, dagli ⭐ e `[ESCLUSO DAL DOCENTE]`, citando entrambe le fonti.
- **Lezioni senza trascrizione.** Per quelle lezioni l'assenza di enfasi non dice nulla. Annotalo in `mappa.md` e basati sugli altri segnali.

## Fonti mancanti

Dichiara nell'introduzione della dispensa quale scala stai usando.

| Fonti disponibili | ⭐⭐⭐ | ⭐⭐ | ⭐ |
|---|---|---|---|
| trascrizioni + esami | regola completa | regola completa | regola completa |
| solo esami | 2+ appelli | 1 appello | resto |
| solo trascrizioni | indicato per l'esame | sottolineato a lezione | resto |
| solo slide | — | — | — |

Con le sole slide non assegnare stelle: sarebbero inventate. Usa invece le etichette `DOMANDA DEL DOCENTE` ed `EVIDENZIATO NELLE SLIDE` (segnali 4 e 5), dichiarandone nell'introduzione la debolezza. Suggerisci all'utente, senza aspettare la risposta per proseguire, dove procurarsi esami delle edizioni precedenti, liste di domande o appunti di chi ha già sostenuto l'esame (vedi SKILL.md, "Input"). Se l'utente ha già detto quali argomenti sono più importanti, usa le sue indicazioni citandole come "indicazione dell'utente". Quando una di queste fonti arriva dopo, aggiungila al registro e ripassa i capitoli per assegnare le stelle.
