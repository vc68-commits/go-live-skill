# go-live-skill

[English](./README.md) · **Italiano**

Skill per [Claude Code](https://claude.com/claude-code) che verifica la prontezza al lancio di un sito o di una web app e produce una checklist con priorità. Questo repo contiene due versioni:

| Skill | Versione | Come lavora | Dipendenze |
|---|---|---|---|
| [`go-live`](./SKILL.md) | 1.5.0 | Il modello lancia `curl`/`dig`/`grep` e compila la checklist | `dig`, `curl`, `python3` |
| [`go-live-v2`](./go-live-v2/SKILL.md) | 2.3.0 | Uno script Python raccoglie i fatti (solo lettura), il modello li interpreta | Python 3.11+; opzionali Playwright, Node.js |

Lo stato di ogni controllo è ✅ / ⚠️ / ❌ / 🔲 (manuale), con priorità **P0** (blocca il lancio) → P1 → P2 → P3.

La v2 non sostituisce la v1: ne riusa le definizioni delle categorie (A–R), le regole di priorità e le note operative. **Installa entrambe.**

> Nota: i file delle skill (`SKILL.md`) sono scritti in italiano. Quando le usi tramite Claude, il report finale è scritto nella **tua lingua** (quella della conversazione o quella che chiedi, es. "report in inglese"). I file `.md`/`.json` scritti da `collect.py` lanciato direttamente da terminale restano in italiano.

---

## Installazione

### Requisiti

- Claude Code installato e funzionante
- `git`
- Per la v1: `curl`, `dig`, `python3`
- Per la v2: `python3` ≥ 3.11 (solo libreria standard, serve `tomllib`)
- Per il modulo browser della v2 (opzionale): Node.js (versione LTS recente) con `npm`, più Playwright e Chromium (vedi sotto)

### 1. go-live (v1)

Le skill di Claude Code stanno in `~/.claude/skills/`. Clona il repo in una cartella di lavoro e collega le due skill:

```bash
git clone git@github.com:vc68-commits/go-live-skill.git ~/projects/go-live-skill
mkdir -p ~/.claude/skills
ln -s ~/projects/go-live-skill ~/.claude/skills/go-live
```

La v1 è la radice del repo (`SKILL.md`). Il link simbolico espone anche la cartella `go-live-v2/` dentro `go-live/`: è innocuo, ma se preferisci evitarlo copia solo i file della v1:

```bash
mkdir -p ~/.claude/skills/go-live
cp ~/projects/go-live-skill/{SKILL.md,README.md,LICENSE.txt} ~/.claude/skills/go-live/
```

### 2. go-live-v2

```bash
ln -s ~/projects/go-live-skill/go-live-v2 ~/.claude/skills/go-live-v2
```

oppure, senza link simbolico:

```bash
cp -R ~/projects/go-live-skill/go-live-v2 ~/.claude/skills/go-live-v2
```

Dopo questo passo la v2 è già utilizzabile: il raccoglitore (`scripts/collect.py`) usa solo la libreria standard di Python.

### 3. Modulo browser della v2 (opzionale)

Serve per i controlli che richiedono un browser reale: banner e cookie prima/dopo il consenso, errori CSP/JS, LCP/CLS/TBT, accessibilità con axe-core, tastiera, layout mobile e Lighthouse. Si attiva con `--browser` o con `[browser] enabled = true` nel file di configurazione.

Lo script cerca le dipendenze **dentro la cartella della skill**, quindi gli ambienti vanno creati lì:

```bash
cd ~/.claude/skills/go-live-v2

# Python: Playwright (versione fissata) e Chromium
python3 -m venv .venv
.venv/bin/pip install "playwright==1.63.0"
.venv/bin/playwright install chromium

# Node: axe-core e Lighthouse (da package.json)
npm install
```

Se usi un link simbolico, queste cartelle (`.venv/`, `node_modules/`) finiscono dentro il repo clonato. **Non committarle**: nel repo non c'è un `.gitignore` per `go-live-v2/`.

Senza il modulo browser, i controlli che lo richiedono compaiono come 🔲 (non eseguiti), mai come superati.

### 4. Verifica

```bash
python3 ~/.claude/skills/go-live-v2/scripts/collect.py --help
```

Poi apri una sessione di Claude Code e digita `/go-live` o `/go-live-v2`: le due skill devono comparire tra quelle disponibili.

---

## Uso

### go-live (v1)

```
/go-live
/go-live https://esempio.com
```

Legge il contesto del progetto (`CLAUDE.md`, `package.json`, file di configurazione), rileva il framework, scansiona il codice, fa i controlli HTTP sul dominio live e salva `GO-LIVE-CHECKLIST.md` nella root del progetto.

### go-live-v2

```
/go-live-v2
/go-live-v2 https://esempio.com
```

Oppure direttamente da terminale, senza passare dal modello:

```bash
python3 ~/.claude/skills/go-live-v2/scripts/collect.py --config go-live.toml --md            # circa 1 minuto
python3 ~/.claude/skills/go-live-v2/scripts/collect.py --config go-live.toml --browser --md  # circa 2,5 minuti
python3 ~/.claude/skills/go-live-v2/scripts/collect.py --url https://esempio.com --md        # senza file di configurazione
```

Opzioni principali: `--config`, `--url`, `--browser`, `--md`, `--no-history`, `--notify`, `--isagentic`, `--ax`. Le ultime tre inviano il dominio a servizi esterni (vedi i commenti nel template).

Ogni esecuzione scrive `~/go-live-test/<dominio>/<data>.json` e `.md` e confronta il risultato con l'esecuzione precedente (peggiorati / migliorati / nuovi). Il raccoglitore fa solo richieste in lettura, a 1 richiesta al secondo, e non modifica mai il sito, il server o il DNS.

### Configurazione per sito

Copia il template accanto al progetto e compilalo:

```bash
cp ~/.claude/skills/go-live-v2/templates/go-live.toml ./go-live.toml
```

I campi essenziali sono `domain` e `url`. Più la configurazione è precisa (`[email].providers`, `auth_via_email`, `[legal].expected_subprocessors`, `[ignore].checks`), più i controlli sono affidabili. Il token per gli avvisi Telegram non va mai nel file `.toml`: sta in `~/.config/go-live/telegram.env`.

---

## Categorie

La v1 definisce 18 categorie (A–R); la v2 ne aggiunge due:

- **S** — coerenza tra fonti (sub-responsabili nella privacy vs fornitori rilevati, provider email dichiarati vs DNS, P.IVA, cookie vs cookie policy)
- **Z** — errori interni dello script (una sezione che va in errore non risulta mai come superata)

Le prime nove, dall'esperienza su bollette.it:

| # | Categoria | Check automatici | Check manuali |
|---|---|---|---|
| A | Infrastruttura & DNS | SSL/HTTPS, redirect | DNS, MX, DKIM/SPF |
| B | Sicurezza | HSTS, CSP, X-Frame, nosniff | Rate limiting, pentest |
| C | SEO Foundation | robots.txt, sitemap, canonical, schema, GA4, GSC meta | GSC verificata, link GA4↔GSC |
| D | GEO / AI | llms.txt, markup AI-friendly | Test dei crawler AI |
| E | Legal & GDPR | pagine Privacy/Termini/Cookie, banner, consent mode | DPO, DPIA, retention policy |
| F | Dati azienda | P.IVA, indirizzo e link legali nel footer | — |
| G | Performance | dimensione bundle, immagini ottimizzate | Lighthouse, CWV |
| H | Content & UX | 404, tag OG, favicon, pagine di errore | Keyword delle landing, gap sui competitor |
| I | Monitoring | Sentry/error tracking, uptime | Alert, revisione dei log |

L'elenco completo, con i singoli controlli, sta in [`SKILL.md`](./SKILL.md).

---

## Aggiornamento

```bash
cd ~/projects/go-live-skill && git pull
```

Se hai copiato i file invece di usare i link simbolici, ripeti la copia dopo il `pull`. Gli ambienti `.venv/` e `node_modules/` della v2 non vengono toccati; riesegui `npm install` solo se cambia `package.json`.

## Licenza

Vedi [`LICENSE.txt`](./LICENSE.txt).
