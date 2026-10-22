# Modelli della dispensa

Contiene i modelli di introduzione, capitolo, blocco esercizio, capitolo di esercitazione e appendici. Le sezioni marcate "se serve" si omettono quando non hanno contenuto. Le altre restano sempre, così lo studente trova le cose nello stesso posto in ogni capitolo.

Nei modelli, due righe in grassetto una sotto l'altra (`**Fonti:**`, `**Priorità:**`) sono separate da una riga vuota: in Markdown due righe consecutive formano un solo paragrafo, e nel PDF e nel DOCX finirebbero sulla stessa riga.

## Indice
1. Introduzione (`00-introduzione.md`)
2. Capitolo (`NN-titolo.md`)
3. Blocco esercizio
4. Capitolo di esercitazione (`90-verso-lo-scritto.md`, se serve)
5. Appendici (`99-appendici.md`)

---

## 1. Introduzione

```markdown
# Introduzione

## Come usare questa dispensa
Due o tre frasi: copre tutte le slide del corso, integra le lezioni e gli esami passati,
le stelle indicano le priorità.

## Legenda
- ⭐⭐⭐ Fondamentale · ⭐⭐ Importante · ⭐ Da sapere (con la definizione di ciascun livello
  e la scala effettivamente usata, vedi importance-rules.md)
- Etichette: RICORRENTE ×N, INDICATO DAL DOCENTE, DOMANDA DEL DOCENTE, EVIDENZIATO NELLE SLIDE
  (solo quelle usate davvero)
- Tag: `[INTEGRAZIONE]`, `[DA VERIFICARE]`, `[DISCREPANZA]`, `[FUORI SLIDE]`, `[SOLUZIONE GENERATA]`,
  `[ESCLUSO DAL DOCENTE]`, tra backtick, con una riga di spiegazione ciascuno
- Citazioni: formato e significato degli ID, con rimando al registro in appendice A

## Com'è fatto l'esame
Modalità, struttura, punteggi e regole (formulario, durata), con citazioni dal programma
e dalle lezioni. Poi l'analisi degli esami passati: quanti appelli, tipi di esercizio
ricorrenti e argomenti più frequenti.

## Fonti disponibili
Quali lezioni hanno la trascrizione, quali esami ci sono e quali hanno le soluzioni.
```

Nella legenda scrivi tra backtick sia gli esempi di citazione (`` `[S01, slide 14]` ``) sia i nomi dei tag (`` `[DA VERIFICARE]` ``): lo script di controllo ignora il testo in codice, così un esempio non viene scambiato per una citazione vera e la legenda non viene contata tra i punti da verificare. Fuori dalla legenda i tag vanno sempre senza backtick, altrimenti spariscono dall'appendice dei punti da verificare.

---

## 2. Capitolo

```markdown
# Capitolo N: Titolo

> **Fonti:** slide S03 1–34 · lezioni T03 (00:00–01:25), T04 (par. 1–12) · 4 esercizi d'esame
>
> **Priorità:** ⭐⭐⭐ · RICORRENTE ×4

## In breve
- 3–7 punti: cosa devi sapere e saper fare alla fine del capitolo, con le stelle.

## Prerequisiti
(se serve) Concetti di altri capitoli, con rimando: "Cap. 2, §2.3".

## N.1 Titolo della sezione ⭐⭐⭐
*Perché ⭐⭐⭐: uscito in 3 appelli [E2023-06, es. 2b]; [E2024-02, es. 1]; [E2025-01, es. 3] e sottolineato a lezione [T03, 00:42:10].*

**Intuizione.** L'idea in parole semplici, spesso con l'esempio o l'analogia usata dal docente [T03, 00:40:15].

**Definizione.** La definizione formale, nei termini delle slide [S03, slide 5].

**Esempio.** Un esempio concreto, preferibilmente quello delle slide o della lezione [S03, slide 6-7].

> 🎓 **Detto a lezione** [T03, 00:42:10]: il docente ha insistito che ... ("questo all'esame lo chiedo sempre").

### N.1.1 Sottosezione
(se serve)

## N.2 Titolo della sezione ⭐
...

## Formule e notazione
| Formula | Simboli | Unità e condizioni | Fonte |
|---|---|---|---|
| $y(t) = K(1 - e^{-t/\tau})$ | $K$ guadagno statico, $\tau$ costante di tempo | $\tau$ in s; vale per $t \ge 0$ | [S03, slide 12] |

## Esercizi su questo argomento
(blocchi esercizio, vedi sotto; prima gli esercizi d'esame, poi quelli svolti a lezione)

## Errori comuni
Errori tipici e trappole, citando quando il docente li ha segnalati.

## Domande del docente
(se serve) Le domande di autoverifica che il docente ha messo nelle slide, con il loro numero
e la citazione, e una risposta modello per ciascuna.

## Domande di autoverifica
Nella forma della modalità d'esame (vedi exam-modes.md), con le risposte o le tracce di risposta.

## Collegamenti
Con quali capitoli si collega e perché.
```

Nei capitoli di teoria senza formule, al posto di "Formule e notazione" usa una tabella **"Concetti chiave"** (termine, definizione, citazione): per uno scritto a domande aperte è il ripasso più utile.

Le risposte modello delle sezioni di domande sono scritte da te: dichiaralo **una volta** in testa alla sezione ("le risposte modello sono state scritte per la dispensa [SOLUZIONE GENERATA]"), invece di ripetere il tag a ogni risposta.

Se una sezione risponde a una domanda del docente, mettilo sotto il titolo, come la riga "Perché" delle stelle: *`DOMANDA DEL DOCENTE` n. 5 [S05, slide 48]*.

Note sul capitolo:
- **Nell'intestazione "Fonti" scrivi le fonti in testo semplice, senza parentesi quadre.** Una citazione come `[S03, slide 1-34]` nell'intestazione farebbe risultare coperte tutte le slide anche se il testo ne salta qualcuna, e il controllo di copertura non servirebbe più.
- Le citazioni stanno nel corpo, vicino al contenuto che sostengono.
- La struttura intuizione, definizione, esempio è un ordine di partenza, non una gabbia: per una procedura o una dimostrazione usa i passi numerati.
- Il riquadro "Detto a lezione" serve per l'enfasi e per spiegazioni importanti del docente, non per ogni frase della trascrizione.

---

## 3. Blocco esercizio

```markdown
### Esercizio tipo A: risposta al gradino di un sistema del primo ordine · RICORRENTE ×3 ⭐⭐⭐

**Dove l'hai visto:**
- Appello del 14/06/2023, file `esami/giugno23.pdf`, esercizio 2b (pag. 3) [E2023-06, es. 2b]
- Appello del 10/02/2024, file `esami/feb24.pdf`, esercizio 1 [E2024-02, es. 1], stessi passaggi con dati diversi
- Svolto a lezione il 12/03/2026: slide `slide/lez05.pdf` 12–14 [S05, slide 12-14], spiegazione a voce [T05, 01:10:20]

**Come riconoscerlo:** cosa nel testo indica che è questo tipo di esercizio.

**Concetti coinvolti:** §4.2, §4.3

**Testo** (appello del 14/06/2023, fedele all'originale):
> ...

**Svolgimento:**
1. ...
2. ...

**Risultato:** ...

**Soluzione:** ufficiale [E2023-06-sol, pag. 2] · oppure: svolta a lezione [T05, 01:10:20] · oppure: [SOLUZIONE GENERATA]

**Varianti negli altri appelli:**
- [E2024-02, es. 1]: chiede anche il tempo di assestamento. Svolgimento: ...
```

Regole per gli esercizi:
- **"Dove l'hai visto" riporta sempre nome del file, data dell'appello e numero dell'esercizio** in chiaro, oltre alla citazione. Lo studente deve poter aprire il file senza consultare il registro.
- Ogni esercizio del catalogo `esercizi.md` compare con la sua citazione in almeno un capitolo. Se coinvolge più capitoli, mettilo in quello del concetto principale e rimandaci dagli altri.
- Lo svolgimento completo va dato almeno una volta per tipo e per ogni variante che introduce un passaggio diverso. Con la modalità "scritto con esercizi" svolgi tutti gli esercizi.
- Se l'esercizio è svolto nelle slide, cita la slide di ogni passo dello svolgimento (`2. Calcoliamo i residui ... [S05, slide 13]`): le citazioni di "Dove l'hai visto" dicono dove trovarlo, ma per il controllo di copertura non spiegano le slide.
- Il testo dell'esercizio è fedele all'originale. Se una parte è illeggibile, `[DA VERIFICARE]`.
- Una soluzione scritta da te è sempre `[SOLUZIONE GENERATA]`, anche quando sei sicuro: lo studente deve sapere che non è stata validata dal docente.

---

## 4. Capitolo di esercitazione

Con lo scritto con esercizi, chi studia vuole anche un capitolo che porti dalla teoria all'esame. Chiamalo `90-verso-lo-scritto.md`, così il numero non cambia se si aggiungono lezioni. Gli svolgimenti completi restano nei capitoli dei concetti: qui si rimanda.

```markdown
# Verso lo scritto

## Com'è fatto lo scritto
Struttura, durata, punteggi, materiale ammesso, con citazioni.

## Gli esercizi degli appelli
| Tipo | Come riconoscerlo | Appelli | Dove è svolto |
|---|---|---|---|
| A | "risposta al gradino" di un G(s) del primo ordine | E2023-06 es. 2b; E2024-02 es. 1 | §4.3 |

## Procedura per tipo
Per ogni tipo, i passi numerati, con rimando allo svolgimento completo.

## Da sapere a memoria
Formule e valori numerici che servono senza formulario (per esempio e⁻¹ ≈ 0,37, se non c'è la calcolatrice).

## Simulazione d'esame
Un compito nello stile degli appelli, con soluzioni [SOLUZIONE GENERATA] dichiarate una volta in testa.
```

---

## 5. Appendici

```markdown
# Appendici

## A. Registro delle fonti
(copia di registro.md, con la riga "Disponibilità delle fonti")

## B. Percorso rapido
Tutte le sezioni ⭐⭐⭐, in ordine, con rimando al paragrafo: cosa studiare se hai poco tempo.

## C. Mappa degli esami
| Tipo | Descrizione | Appelli | Ricorrenza | Capitolo | Priorità |
|---|---|---|---|---|---|
| A | Risposta al gradino, primo ordine | E2023-06 es. 2b; E2024-02 es. 1; E2025-01 es. 3 | ×3 | 4 | ⭐⭐⭐ |

Poi gli argomenti più frequenti negli esami, ordinati per numero di appelli.

## D. Glossario
Termine, definizione breve, paragrafo in cui è spiegato.

## E. Indice delle formule
Formula, significato, paragrafo.

## F. Slide di servizio
Slide senza contenuto da spiegare (titolo, indice, ringraziamenti, "domande?"),
con la loro citazione: [S01, slide 1-2]; [S02, slide 13].
```

Scrivi la sezione delle slide di servizio appena fatta la mappa, anche se il resto delle appendici viene alla fine: senza di essa anche i controlli parziali segnalano come mancanti le slide di titolo.

Dopo `99-appendici.md`, `merge_book.py` aggiunge le due appendici generate da `check_coverage.py`: "Punti da verificare" (`--tag-report`, in `punti-da-verificare.md`: tutti i tag, raggruppati per tipo, con la sezione in cui compaiono) e "Copertura delle slide" (`--copertura`, in `copertura.md`: per ogni slide, la sezione che la spiega). Non scriverle a mano e non dar loro una lettera.
