---
name: go-live-v2
description: "Go-live readiness audit v2 per siti e web app. Un raccoglitore deterministico (script Python, solo richieste in lettura) esegue i controlli verificabili dall'esterno su 19 categorie (infrastruttura/DNS/email, sicurezza, SEO, GEO, legale/GDPR, azienda, performance, UX, accessibilità, monitoring, form, link, hreflang, SEO on-page, immagini, E-E-A-T) e incrocia le fonti (privacy vs fornitori reali, SPF/DKIM vs provider email, P.IVA, cookie). Poi il modello interpreta, delega gli approfondimenti SEO ai subagent e produce checklist ✅/⚠️/❌/🔲 con priorità P0-P3 e variazioni rispetto all'ultima esecuzione. Usalo quando l'utente dice: go-live v2, audit di lancio, controlla il sito prima del lancio, pronto per produzione, health check del sito, checklist lancio."
user-invokable: true
argument-hint: "[url-o-dominio] [--config percorso/go-live.toml] [--save]"
license: MIT
metadata:
  version: "2.0.0"
  category: launch
  requires: "python3 >= 3.11 (solo libreria standard)"
---

# Go-Live v2 — raccolta deterministica + interpretazione

Evoluzione di `go-live` (v1.4). Le **definizioni delle categorie A-R, le regole di priorità (P0-P3), l'ordine di
remediation email, la nota su DNSSEC e le "Note operative"** restano quelle di `~/.claude/skills/go-live/SKILL.md`:
rileggile quando serve (sezioni "Step 3.2", "Logica priorità", "Note operative"). Qui cambia il **metodo**:

| | v1 | v2 |
|---|---|---|
| Raccolta fatti | il modello lancia curl/dig/grep come gli viene | **script** (`scripts/collect.py`), ripetibile e senza modello |
| Conteggi/score | stimati dal modello | **calcolati dallo script** |
| Copertura pagine | 1-2 pagine | **campione dalla sitemap** (default 24 pagine, richieste cortesi) |
| Coerenza tra fonti | prosa nelle note | **categoria S**: privacy ↔ fornitori reali, SPF/DKIM ↔ provider, P.IVA, cookie |
| Cronologia | nessuna | **JSON per ogni esecuzione + confronto** con la precedente |
| Configurazione | nessuna | **`go-live.toml`** per sito (provider, eccezioni, soglie) |

## Regole non negoziabili

- **Solo lettura.** Nessuna correzione automatica, nessuna scrittura sul sito/server/DNS. Segnala, poi chiedi.
- **Un controllo non eseguito o fallito non è un controllo superato.** Se lo script riporta `[ERRORE…]`, `Z00` o 🔲, non trasformarlo in ✅/❌.
- **Non ricalcolare i conteggi:** usa quelli dello script.
- **Verifica a mano le segnalazioni pesanti prima di riferirle** (P0 e ❌): un secondo comando indipendente
  (`dig +short … @1.1.1.1`, `curl`) basta. Un fallimento DNS locale singolo NON è un link/dominio rotto.
- **Legale/GDPR:** segnalazioni tecniche, mai giudizi legali.
- **Verifica gli identificatori esatti prima di raccomandarli** (include SPF, selettori DKIM): risolvili con `dig`.

## Processo

### Step 0 — Configurazione

Cerca nell'ordine: argomento `--config`, `./go-live.toml`, `./.claude/go-live.toml`, `../go-live.toml`.
Se non esiste, crea una bozza da `~/.claude/skills/go-live-v2/templates/go-live.toml` compilando dominio/URL
(dai file del progetto o chiedendolo) e **chiedi all'utente di confermare** i campi che non puoi dedurre:
`[email].providers`, `auth_via_email`, `[legal].expected_subprocessors`. Salvala accanto al progetto (non dentro un repo
senza chiedere). Se l'utente passa solo un URL, usa `--url`.

### Step 1 — Raccolta (script)

```bash
python3 ~/.claude/skills/go-live-v2/scripts/collect.py --config <go-live.toml> --browser --md
```
Senza `--browser` dura circa 1 minuto (richieste cortesi, ~1 al secondo); con `--browser` (consigliato) circa 2,5 minuti
perché aggiunge Chromium, axe-core e Lighthouse: usa un timeout ampio (10 minuti) o lancialo in background. Scrive `~/go-live-test/<dominio>/<data>.json`
e `.md`; stampa il report Markdown. `--no-history` salta il confronto con l'esecuzione precedente.

### Step 2 — Codice del progetto (se sei dentro un progetto)

Se la cartella corrente è un progetto (package.json, next.config, ecc.), esegui lo scan del codice descritto in
`go-live/SKILL.md` Step 1-2: serve a vedere ciò che dall'esterno non si vede (config degli header, componenti
banner/consenso, rate limiting, `.env` non hardcoded, dipendenze → sub-responsabili reali). **Incrocia** con lo script:
dipendenze/servizi nel codice che non compaiono nell'elenco della privacy sono P0 (S01).

### Step 3 — Approfondimenti SEO con subagent

Usa lo strumento **`Agent`** (non `Task`) con `subagent_type`, in parallelo, passando il percorso del JSON e **solo
ciò che lo script non può sapere** (qualità dei contenuti, E-E-A-T, schema in profondità, GEO):

| Subagent | Chiedi |
|---|---|
| `seo-technical` | crawlability, indicizzabilità, JS rendering, mobile (lo script ha già robots/sitemap/canonical) |
| `seo-schema` | validazione Schema.org in profondità e markup mancante |
| `seo-geo` | citabilità dei passaggi, AI visibility |
| `seo-content` | qualità, E-E-A-T, thin content, solo se ci sono articoli/guide |
| `seo-local` / `seo-ecommerce` | solo se il sito lo richiede |

`seo-images` e `seo-hreflang` esistono come **skill**, non come agent: invoca la skill o ignora (lo script copre le basi).
Prompt tipo: `URL: …  Dati già raccolti: <json>. Restituisci SOLO i punti in più rispetto ai fatti già raccolti, formato ✅/⚠️/❌/🔲, max 300 parole. Non fare un audit standalone.`

### Step 4 — Report

1. **Intestazione** e **SCORE** dello script (copiali tali e quali).
2. Le categorie A-S dello script, con i punti aggiuntivi dei subagent marcati `(seo-xxx)` e quelli dello scan codice `(codice)`.
3. **Priorità P0-P3**: quelle dello script, riordinate con il tuo giudizio; per ogni P0 e ❌: prova (il comando/risultato), impatto, correzione proposta.
4. **Interpretazione** (breve): cause comuni, ordine consigliato degli interventi (per l'email: SPF → DKIM → DMARC in due tempi, come in v1), cosa serve per chiudere i 🔲 (browser, accessi GSC/GA4, prova di consegna email).
5. **Variazioni** rispetto all'ultima esecuzione (se presenti).
6. Chiudi con i **10 interventi consigliati** in ordine.

### Step 5 — Salvataggio

Se `--save` o l'utente accetta: scrivi `GO-LIVE-CHECKLIST.md` nella cartella del progetto con intestazione, categorie,
score e sezione "Changelog" (regressioni/miglioramenti per data).

## Prontezza per gli agenti AI (categoria D, D05–D12)

Aggiunti nella 2.1.0 sulla base dei controlli "Is Agentic". Solo richieste in lettura (qualche `GET` in più con
`Accept: text/markdown`).

| ID | Controllo | Note |
|---|---|---|
| D05 | 404 con corpo Markdown | stato 404, `Content-Type: text/markdown`, ≥ 20 caratteri e un link a docs/sitemap/`llms.txt` |
| D06 | Negoziazione Markdown sulla home | `text/markdown` + `Vary: Accept`; con `Accept: text/html` resta HTML |
| D07 | Come D06 su 3 pagine della sitemap | |
| D08 | Sezione "when to use / quando usare" | in `llms.txt`, oppure `/AGENTS.md`; ≥ 150 caratteri di casi d'uso |
| D10 | Pagine di fiducia | about, contact, privacy con ≥ 500 caratteri di testo (soglia `trust_min_chars`) |
| D11 | Il browser non riceve mai Markdown | `Accept` da browser e `*/*` devono dare HTML: protegge dalla cache che serve Markdown agli utenti |
| D12 | Brand discoverability | sempre 🔲: serve una ricerca web / Search Console |

D05, D06, D07 e D11 si applicano solo se il sito serve Markdown: con `[agent].markdown` non impostato la skill lo
rileva dalla home e, se non lo serve, li segna ➖ (opzionale). Con `markdown = true` l'assenza diventa un fallimento.
Organization (`contactPoint`, `address`) è già coperta da R02–R05.

### Passo opzionale: Is Agentic (`--isagentic`) — consigliato per i siti di contenuti

`collect.py --isagentic` (oppure `[agent].isagentic = true`) legge l'ultimo report pubblico di
[is-agentic.com](https://is-agentic.com) (Vercel, motore Ora) con `GET /api/v1/report?url=<dominio>` (OpenAPI:
`https://is-agentic.com/openapi.json`). **Sola lettura: non avvia scansioni** (l'API non lo permette e la CLI
`is-agentic` scansiona solo se non esiste alcun report); per aggiornare il risultato dopo una modifica del sito si rilancia
la scansione dalla pagina web. Il dominio viene inviato a is-agentic.com: per questo è spento di default, stampa un avviso
su stderr e aggiunge una nota nel report. Limite: 120 richieste/min per IP, nessuna chiave.

- Il punteggio (0-100: Essential 80, Recommended 20, Bonus fino a 5) **esclude i controlli non applicabili**, quindi non penalizza
  i siti senza API: è la misura giusta per un sito di contenuti (a differenza di `ax`).
- **Y01** punteggio, breakdown per tier, controlli applicabili ed **età della scansione**; con `isagentic_min_score` (default 90)
  diventa ✅/⚠️, e segnala «possibilmente obsoleta» oltre `isagentic_max_age_h` (default 24 h).
- **Y-<id>** un controllo per ogni problema del report: Essential fallito = ❌ P1, Recommended = ⚠️ P2, Bonus = P3, con
  evidenza e raccomandazione di Ora.
- Nessun report per il dominio: Y01 🔲 con l'invito a scansionare da is-agentic.com. Quota esaurita o risposta illeggibile: **Z04** 🔲.

### Passo opzionale: Ora `ax` (`--ax`) — INVIA IL DOMINIO A UN SERVIZIO ESTERNO (poco pertinente ai siti senza API)

`collect.py --ax` (oppure `[agent].ax = true`) esegue `npx --yes ax@0.10.1 audit <url> --json` (CLI di Ora, lo stesso
servizio dello scanner "Is Agentic"). **È l'unico passo che esce dalla regola "tutto locale": il dominio viene inviato a
ora.ai**; per questo è spento di default, stampa un avviso su stderr e aggiunge una nota nel report. Nessuna chiave API,
nessun tunnel (le variabili `ORA_*` dell'ambiente vengono ignorate), versione del pacchetto fissata.

- **X01** punteggio e grado di `ax`, con i punteggi per livello. È 🔲 informativo; con `ax_min_score` diventa ✅/⚠️.
- **X-<id>** i "top fix" di Ora (default 6), 🔲 P3 con la raccomandazione e i punti stimati.
- `--ax-force` ignora la cache di Ora (budget: 6 scansioni forzate al giorno).
- Se `npx` manca, va in timeout o Ora risponde con un errore: **Z03** (🔲), non un fallimento del sito.

Come leggerlo: il modello di `ax` è costruito per prodotti con API (MCP, OAuth, OpenAPI, SDK, pagamenti agentici). Su un
sito di contenuti il punteggio assoluto è basso per costruzione (bollette.it: 37/100 con Is Agentic a 98). Contano i top
fix applicabili (Link header, `.md`, frontmatter, schema, sameAs), non il numero. Per questo i risultati restano 🔲 e non
entrano nel conteggio ✅/⚠️/❌.

## Modulo browser (`--browser`, `scripts/browser.py`)

Chromium headless (Playwright) nell'ambiente `.venv` della skill, più `axe-core` e `lighthouse` in `node_modules`.
Non invia form né modifica nulla. Controlla: banner cookie reale (pulsante «Rifiuta» al primo livello), cookie e invii di
dati **prima** del consenso (distingue il caricamento di `gtag.js`, normale con Consent Mode, dagli invii veri `/g/collect`),
effetto di «Rifiuta» e «Accetta», cookie impostati contro la cookie policy, errori CSP/JS in console, richieste fallite,
LCP/CLS/TBT di laboratorio, **axe-core** (WCAG 2.2 AA, contrasto), navigazione da tastiera e skill link, layout mobile
(scorrimento orizzontale, aree di tocco), **Lighthouse** mobile e desktop (Performance, Accessibilità, Best Practices, SEO).
I dati sono **di laboratorio, dal server di audit**: non sono dati reali degli utenti (CrUX/RUM). Screenshot in
`~/go-live-test/<dominio>/shots/`. Se non è installato (`.venv` mancante) l'esecuzione prosegue con `Z02` e i 🔲 al loro posto.

## Esecuzione: solo su richiesta

La skill **non ha nessuna esecuzione automatica o periodica**: si lancia solo quando l'utente lo chiede
(`/go-live-v2` o il comando `collect.py`). Non proporre timer o cron e non installarne.

Opzionale: `--notify` manda un avviso Telegram a fine esecuzione **solo se qualcosa è peggiorato** rispetto alla volta
precedente, il certificato scade entro 30 giorni o è la prima esecuzione (`[notify].mode = "always"` per riceverlo sempre).
Funziona solo se esiste `~/.config/go-live/telegram.env` (`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, permessi 600) con un bot
dedicato creato con @BotFather; senza, l'avviso viene scritto in `~/go-live-test/<dominio>/last-notify.txt`. Non usare i
token dei bot di trading.

## Cosa lo script non vede (resta 🔲 o Step 2/3)

Dati reali degli utenti (CrUX/INP), dati di Search Console e GA4, consegna reale delle email, backup/rollback,
validazione server-side e rate limiting dei form, test con screen reader, revisione legale.

## Esempi

```
/go-live-v2                         → audit del progetto corrente (cerca go-live.toml)
/go-live-v2 bollette.it             → audit con dominio indicato
/go-live-v2 --config ../go-live.toml --save
```
