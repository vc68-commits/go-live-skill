---
name: go-live
description: "Go-live readiness agent for web apps and sites. Audits all launch-critical activities across 18 categories: infrastructure/DNS, security, SEO, GEO/AI, legal/GDPR, company info, performance, content/UX, accessibility, monitoring, email, forms/anti-spam, link checker, hreflang, backup, SEO on-page, image SEO, E-E-A-T. For SEO-specific categories (C, D, N, P, Q, R) delegates to specialist subagents (seo-technical, seo-schema, seo-geo, seo-images, seo-hreflang, seo-local, seo-ecommerce, seo-content) for deeper analysis. Produces a prioritized checklist with ✅/⚠️/❌/🔲 status. Run at any time to track launch readiness and identify blockers. Invoke when user says: go-live, go live, checklist lancio, pronto per produzione, launch checklist, or similar."
user-invokable: true
argument-hint: "[url]"
license: MIT
metadata:
  author: bollette.it
  version: "1.4.0"
  category: launch
---

# Go-Live Readiness Audit

## Scopo

Verificare che un sito/app sia pronto per il lancio in produzione, monitorando tutte le attività critiche. Utilizzabile sia la prima volta (onboarding) sia come check periodico (monitoring).

---

## Processo

### Step 1 — Raccolta contesto progetto

Leggi (in parallelo):
- `CLAUDE.md`, `AGENTS.md`, `.claude/` — istruzioni progetto
- `package.json` (o `requirements.txt`, `go.mod`, ecc.) — framework e dipendenze
- `next.config.ts` / `next.config.js` / `nginx.conf` / `_headers` — config security
- `src/app/layout.tsx` o file layout principale — GA4, meta globali
- `public/` — robots.txt, sitemap.xml, llms.txt, favicon files

**Rileva**:
- Framework: Next.js / Nuxt / SvelteKit / Astro / Express / Django / static
- URL del sito (da CLAUDE.md, package.json `homepage`, o chiedi all'utente)
- Stack: TypeScript/JS, Python, Go, ecc.

Se l'URL non è disponibile nel progetto, chiedi all'utente: "Qual è l'URL live del sito?"

### Step 2 — Scan codebase (grep automatico)

Esegui i seguenti check leggendo i file del progetto:

**Sicurezza (cerca in config files)**:
```bash
grep -r "Strict-Transport-Security" . --include="*.ts" --include="*.js" --include="*.conf" -l
grep -r "Content-Security-Policy" . --include="*.ts" --include="*.js" --include="*.conf" -l
grep -r "X-Frame-Options" . --include="*.ts" --include="*.js" -l
grep -r "X-Content-Type-Options" . --include="*.ts" --include="*.js" -l
grep -r "Referrer-Policy" . --include="*.ts" --include="*.js" -l
```

**SEO Foundation**:
```bash
# robots.txt
find . -name "robots.txt" -not -path "*/node_modules/*"
find . -name "robots.ts" -not -path "*/node_modules/*"
# sitemap
find . -name "sitemap.xml" -not -path "*/node_modules/*"
find . -name "sitemap.ts" -not -path "*/node_modules/*"
# llms.txt
find . -name "llms.txt" -not -path "*/node_modules/*"
# Google Search Console meta tag
grep -r "google-site-verification" . --include="*.tsx" --include="*.ts" --include="*.html" -l
# GA4
grep -r "G-[A-Z0-9]" . --include="*.tsx" --include="*.ts" --include="*.html" -l
# Canonical
grep -r "canonical" . --include="*.tsx" --include="*.ts" -l
# Schema.org
grep -r "application/ld+json" . --include="*.tsx" --include="*.ts" -l
# OG tags
grep -r "openGraph\|og:image\|og:title" . --include="*.tsx" --include="*.ts" -l
# Twitter/X card
grep -r "twitter:card\|twitter:title\|twitter:image" . --include="*.tsx" --include="*.ts" --include="*.html" -l
# Hreflang
grep -r "hreflang" . --include="*.tsx" --include="*.ts" --include="*.html" -l
```

**Legal & GDPR**:
```bash
# Pagine legali (Next.js App Router)
find . -path "*/app/privacy*" -name "page.tsx"
find . -path "*/app/termini*" -name "page.tsx"
find . -path "*/app/cookie*" -name "page.tsx"
# Cookie banner
grep -r "CookieBanner\|cookie-banner\|cookieBanner" . --include="*.tsx" --include="*.ts" -l
# Consent Mode v2
grep -r "consent.*update\|gtag.*consent" . --include="*.tsx" --include="*.ts" -l
# Email privacy
grep -r "privacy@" . --include="*.tsx" --include="*.ts" --include="*.html" -l
```

**Company info (footer)**:
```bash
grep -r "P\.IVA\|VAT\|partita iva\|società\|Srl\|SpA\|Ltd\|GmbH" . --include="*.tsx" --include="*.ts" --include="*.html" -l
grep -r "Via \|Piazza \|Viale \|Street \|Address" . --include="*.tsx" --include="*.ts" -l
# Telefono
grep -r "tel:\|telefon\|phone\|+39" . --include="*.tsx" --include="*.ts" --include="*.html" -l
```

**Content & UX**:
```bash
# 404 page
find . -name "not-found.tsx" -o -name "404.tsx" -o -name "404.html" | grep -v node_modules
# Error page
find . -name "error.tsx" -o -name "500.tsx" -o -name "500.html" | grep -v node_modules
# Favicon
find ./public -name "favicon*" -o -name "icon*" 2>/dev/null | head -10
# Copyright year aggiornato
grep -rn "©\|&copy;\|copyright" . --include="*.html" --include="*.tsx" | grep -E "202[0-3]" | head -5
```

**Accessibilità**:
```bash
# Skip link
grep -r "skip-link\|skip-to-content\|skipLink\|skip-main" . --include="*.html" --include="*.tsx" --include="*.ts" -l
# ARIA labels
grep -r "aria-label\|aria-labelledby" . --include="*.html" --include="*.tsx" -l
# Immagini senza alt (segnala quelle sospette)
grep -rn "<img " . --include="*.html" --include="*.tsx" | grep -v 'alt=' | head -5
# HTML senza lang attribute
grep -rn "<html " . --include="*.html" | grep -v 'lang=' | head -5
# Dichiarazione accessibilità
find . \( -name "accessibility*" -o -name "accessibilita*" \) -not -path "*/node_modules/*"
# Focus visible in CSS
grep -r ":focus\|:focus-visible" . --include="*.css" -l
```

**Email transazionale**:
```bash
grep -r "smtp\|nodemailer\|PHPMailer\|sendmail\|mail(" . --include="*.php" --include="*.ts" --include="*.js" -l
grep -r "send_mail\|sendMail\|send-mail" . --include="*.php" --include="*.ts" --include="*.html" -l
```

**Form & Anti-spam**:
```bash
grep -r "honeypot\|recaptcha\|hcaptcha\|turnstile" . --include="*.php" --include="*.ts" --include="*.html" --include="*.tsx" -l
grep -r "rate.limit\|rateLimit\|throttle" . --include="*.php" --include="*.ts" -l
```

**Hreflang**:
```bash
grep -r "hreflang" . --include="*.html" --include="*.tsx" --include="*.ts" -l
# Verifica coppie (ogni pagina deve dichiarare tutte le lingue)
grep -rn 'hreflang=' . --include="*.html" | head -10
```

**Monitoring**:
```bash
grep -r "sentry\|@sentry\|Sentry" . --include="*.ts" --include="*.tsx" --include="*.json" -l
grep -r "uptimerobot\|betterstack\|cronitor\|statuspage" . --include="*.ts" --include="*.tsx" -l
```

**SEO On-Page**:
```bash
# H1 presence and uniqueness
grep -rn "<h1" . --include="*.html" --include="*.tsx" | head -5
# OG image dimensions declared
grep -rn "og:image:width\|og:image:height" . --include="*.html" --include="*.tsx" | head -5
# noindex/nofollow usage
grep -rn "noindex\|nofollow" . --include="*.html" --include="*.tsx" | grep -v node_modules | head -10
# URL structure: no underscores in routes
find . -path "*/app/*" -name "page.tsx" | grep "_" | grep -v node_modules | head -5
```

**Image SEO**:
```bash
# Immagini senza alt
grep -rn "<img " . --include="*.html" --include="*.tsx" | grep -v 'alt=' | head -10
# Immagini senza lazy loading
grep -rn "<img " . --include="*.html" --include="*.tsx" | grep -v 'loading=' | grep -v 'LazyLoad\|lazy' | head -5
# WebP/AVIF usage
grep -r "\.webp\|\.avif\|type=\"image/webp\"\|type=\"image/avif\"" . --include="*.html" --include="*.tsx" -l
# Image sitemap
find . -name "sitemap*image*" -o -name "image*sitemap*" | grep -v node_modules | head -3
```

**E-E-A-T & Trust**:
```bash
# About / Chi siamo page
find . \( -path "*/app/about*" -o -path "*/app/chi-siamo*" \) -name "page.tsx" | grep -v node_modules | head -3
# Author pages
find . \( -path "*/app/author*" -o -path "*/app/autore*" \) -name "page.tsx" | grep -v node_modules | head -3
# ethicsPolicy / editorial policy in Schema.org
grep -r "ethicsPolicy\|editorial\|codice-etico" . --include="*.tsx" --include="*.ts" --include="*.html" -l
# sameAs social profiles in Schema.org
grep -r "sameAs" . --include="*.tsx" --include="*.ts" --include="*.html" -l
# Author bylines
grep -r "author\|byline\|firmato\|redazione" . --include="*.tsx" --include="*.ts" -l | head -5
```

### Step 3 — HTTP check sul dominio live

Esegui i check HTTP sull'URL del sito:

```bash
# Security headers
curl -sI "https://$URL" | grep -iE "(strict-transport|content-security|x-frame|x-content-type|referrer-policy|permissions-policy)"

# Redirect HTTP→HTTPS
curl -sI "http://$URL" | grep -i "location"

# robots.txt accessibile
curl -s "https://$URL/robots.txt" | head -5

# sitemap.xml accessibile
curl -s "https://$URL/sitemap.xml" | head -3

# llms.txt accessibile
curl -s "https://$URL/llms.txt" | head -3

# GSC meta tag
curl -sL "https://$URL" | grep -i "google-site-verification"

# SSL info
curl -sI "https://$URL" --max-time 5 | head -3

# Link checker base (solo link interni)
wget --spider -r --no-parent -q "https://$URL" 2>&1 | grep "404\|broken" | head -10

# SEO On-Page: H1 e og:image dimensions
curl -sL "https://$URL" | grep -iE "<h1|og:image:(width|height)"

# E-E-A-T: About e Author pages
curl -sI "https://$URL/about" --max-time 5 | head -2
curl -sI "https://$URL/chi-siamo" --max-time 5 | head -2
curl -sI "https://$URL/author" --max-time 5 | head -2
```

### Step 3.2 — DNS & Email deliverability (sempre, se c'è un dominio)

⚠️ **Questi check vanno eseguiti, non lasciati a 🔲.** SPF/DKIM/DMARC sono voci di checklist facili da
marcare "da verificare a mano" e non verificare mai: su un progetto reale un SPF **completamente assente**
è rimasto invisibile per mesi proprio così. Sono tre comandi: eseguili.

🚨 **Usa DNS-over-HTTPS, non `dig`.** In ambienti sandboxed/aziendali `dig` fallisce silenziosamente
restituendo output **vuoto**, indistinguibile da "record assente". Verificato su un caso reale: `dig` dava
vuoto per MX e DMARC, mentre entrambi esistevano — un audit basato su `dig` li avrebbe dichiarati assenti.
DoH passa da HTTPS e aggira il problema.

⚠️ **Estrai solo la sezione `Answer`.** Su un record inesistente (NODATA) la risposta contiene comunque un
`"data"` — il **SOA** nella sezione `Authority`. Un `grep '"data"'` generico lo scambia per un record
trovato: testandolo, riportava "DKIM presente" per 9 selettori tutti inesistenti. `ans()` sotto evita questo.

```bash
D="$URL"   # dominio nudo, senza https:// né www

# Restituisce SOLO i record della sezione Answer.
# Vuoto = record davvero assente. Query fallita = lo dice esplicitamente, così non la scambi per "assente".
ans() {
  curl -s -m 20 "https://dns.google/resolve?name=$1&type=$2" | python3 -c '
import sys, json
try:
    d = json.load(sys.stdin)
except Exception:
    print("[ERRORE: nessuna risposta DNS - non concludere nulla]"); sys.exit(1)
st = d.get("Status")
if st == 3:
    print("[NXDOMAIN: il nome non esiste]"); sys.exit(0)
if st != 0:
    print("[QUERY FALLITA Status=%s - non concludere nulla]" % st); sys.exit(1)
for a in d.get("Answer", []):
    print(a["data"])
'
}

# ── Sanity check: la catena DNS risponde?
ans "$D" A

# ── SPF: deve esistere UN SOLO record v=spf1 sull'apex
ans "$D" TXT | grep -i "v=spf1"

# ── DMARC
ans "_dmarc.$D" TXT | grep -i "v=DMARC1"

# ── MX (se il dominio riceve posta)
ans "$D" MX

# ── DKIM: i selettori non sono indovinabili dall'esterno.
#    Provane alcuni comuni; l'assenza NON prova che manchi → verificare nella console del provider.
for s in default google selector1 selector2 k1 mail smtp s1 s2; do
  r=$(ans "$s._domainkey.$D" TXT | grep -i "v=DKIM1\|p=" | head -1)
  [ -n "$r" ] && echo "DKIM $s → ${r:0:70}"
done

# ── Se SPF esiste: conta i lookup DNS (limite rigido = 10, oltre il quale SPF va in permerror)
ans "$D" TXT | grep -i "v=spf1" | grep -o "include:[^ \"]*" | wc -l
```

`ans()` distingue da sola i tre casi: **output vuoto** = record assente (NODATA, `Status:0` senza
`Answer`) · **`[NXDOMAIN]`** = il nome non esiste · **`[QUERY FALLITA]`/`[ERRORE]`** = non hai un dato,
quindi non scrivere nulla nel report. Se una query fallisce, ricontrolla con
`dig +short <tipo> <nome> @1.1.1.1` come seconda fonte; se le due discordano, fidati di DoH.

**Come valutare i risultati:**

| Esito | Stato | Nota |
|---|---|---|
| Nessun `v=spf1` | ❌ | Grave se il sito invia email. **Critico** se l'autenticazione è via magic link / OTP: l'email *è* il login, se va in spam l'utente non entra e non lo segnala |
| Due o più record `v=spf1` | ❌ | Si invalidano a vicenda: SPF risulta permerror. Fonderli in uno |
| SPF con `?all` o senza `all` | ⚠️ | Nessuna policy effettiva |
| SPF con >10 `include:` | ❌ | Superato il limite di lookup, SPF fallisce |
| Nessun `_dmarc` | ❌ | |
| DMARC `p=none` **senza** `rua=` | ⚠️ | Non protegge e non raccoglie report: decorativo |
| DMARC `p=quarantine`/`reject` ma SPF assente | 🔴 | **Blocca le email legittime del sito stesso** |
| MX presente ma nessun SPF | ❌ | Dominio che riceve e invia senza autenticazione |

**Ordine corretto di remediation** — da riportare sempre nel report, perché invertirlo causa un outage email:

1. Prima **SPF**, includendo *tutti* i mittenti (provider transazionale **e** provider delle caselle)
2. Poi **DKIM** dalla console del provider (record CNAME/TXT da pubblicare)
3. **DMARC in due tempi**: `p=none; rua=mailto:…` per 2-4 settimane → si leggono i report → solo allora
   `p=quarantine`. Mai alzare la policy prima che SPF e DKIM siano verificati e allineati
4. La casella indicata in `rua=` **deve esistere**, altrimenti i report rimbalzano

> ⚠️ **Verificare l'esattezza degli `include:` prima di raccomandarli.** Gli hostname SPF dei provider sono
> facili da sbagliare a memoria: su un caso reale `_spf.qboxmail.com` (con underscore, suggerito a memoria)
> **non esiste** — quello valido è `spf.qboxmail.com`. Controllare sempre che l'include risolva davvero,
> prima di metterlo in un report: `dig +short TXT spf.<provider>.com`

**Non confondere una zona non firmata con DNSSEC rotto.** Un `SERVFAIL` che sparisce con `dig +cd` sembra
un DS orfano, ma prima di dichiararlo va verificata l'esistenza del DS:

```bash
curl -s "https://dns.google/resolve?name=$D&type=DS"   # nessun "Answer" ⇒ nessun DS ⇒ zona insecure, ok
curl -s "https://dns.google/resolve?name=$D&type=A"    # Status:0 ok · 2 SERVFAIL · 3 NXDOMAIN
```

`AD:false` significa "non autenticato", **non** "errore". Se non c'è DS, DNSSEC non è in gioco e il
SERVFAIL viene dalla rete locale di chi sta indagando.

### Step 3.5 — Delegazione SEO Specialist (se URL disponibile)

Quando è disponibile un URL live, lancia i seguenti subagent **in parallelo** con il tool Agent:

**Sempre (per qualsiasi sito con URL live):**

| Subagent | Sezioni coperte | Prompt da passare |
|---|---|---|
| `seo-technical` | C (robots/sitemap/canonical), P (URL structure, noindex) | "Audit tecnico SEO per [URL]. Focus: crawlability, indexability, URL structure, mobile, JS rendering. Output: ✅/❌/⚠️ per ogni check, max 400 parole." |
| `seo-schema` | C (Schema.org), R (contactPoint, sameAs, address) | "Detect e valida Schema.org per [URL]. Output: tipi trovati, errori critici, markup mancante. Max 300 parole." |
| `seo-geo` | D (llms.txt, AI crawlers, AI visibility) | "Analisi GEO/AI visibility per [URL]. Focus: llms.txt compliance, robots.txt AI policies, AI Overviews readiness. Max 300 parole." |
| `seo-images` | Q (alt text, WebP/AVIF, lazy loading, og:image) | "Audit Image SEO per [URL]. Focus: alt text, formati moderni, lazy loading, og:image dimensions. Max 300 parole." |

**Condizionali (lancia solo se rilevato in Step 1):**

| Condizione rilevata | Subagent da aggiungere |
|---|---|
| `hreflang` nel codice o multilingua evidente | `seo-hreflang` |
| Sito local business (indirizzo, orari, telefono) | `seo-local` |
| Sito e-commerce (WooCommerce, Shopify, /prodotti, /shop) | `seo-ecommerce` |
| Blog / news / articoli con autori | `seo-content` |
| URL specifico non-homepage passato come argomento | `seo-page` |

**Come invocare i subagent:**

Usa il tool Agent con `subagent_type` uguale al nome del subagent (es. `"seo-technical"`). Passa come `prompt`:
```
URL: [URL]
[descrizione focus dal campo "Prompt da passare" della tabella]
Sei chiamato dal go-live audit: restituisci SOLO i check rilevanti per le sezioni indicate, formato ✅/❌/⚠️/🔲. Non produrre un full audit standalone.
```

**Integrazione risultati:**
- Usa i risultati di `seo-technical` per compilare le sezioni **C** e **P**
- Usa i risultati di `seo-schema` per la parte Schema.org di **C** e **R**
- Usa i risultati di `seo-geo` per la sezione **D**
- Usa i risultati di `seo-images` per la sezione **Q**
- Usa i risultati dei subagent condizionali per le rispettive sezioni (**N**, **R**)
- I tuoi grep/curl di Step 2-3 rimangono validi per le sezioni non SEO (A, B, E, F, G, H, I, J, K, L, M, O)

---

### Step 4 — Analisi dei risultati e report

Per ogni item, assegna uno stato:
- **✅** — implementato e verificato
- **⚠️** — parziale o richiede attenzione
- **❌** — mancante
- **🔲** — richiede verifica manuale (non verificabile automaticamente)

---

## Report — Struttura Output

Produce il seguente formato (adatta i valori trovati):

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🚀 GO-LIVE CHECKLIST — [Nome Progetto]
   URL: [url] | Framework: [framework] | Data: [data]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

### A. INFRASTRUTTURA & DNS
[✅/❌] HTTPS attivo e SSL valido
[✅/❌] Redirect HTTP → HTTPS (301/308)
[✅/❌] Redirect www → apex (o viceversa)
[🔲] DNS: A record propagato
[✅/❌] Email dominio: MX configurato                          ← Step 3.2, verificato con dig
[✅/❌] SPF: presente, singolo, ≤10 lookup                     ← Step 3.2, verificato con dig
[✅/❌] DMARC: presente, con rua= per i report                 ← Step 3.2, verificato con dig
[✅/❌/🔲] DKIM: selettori pubblicati                          ← 🔲 solo se i selettori non sono ispezionabili

### B. SICUREZZA
[✅/❌] HSTS (Strict-Transport-Security)
[✅/❌] CSP (Content-Security-Policy)
[✅/❌] X-Frame-Options: DENY
[✅/❌] X-Content-Type-Options: nosniff
[✅/❌] Referrer-Policy
[✅/❌] Permissions-Policy
[🔲] Rate limiting su API sensibili
[🔲] No dati sensibili in bundle JS frontend

### C. SEO FOUNDATION
[✅/❌] robots.txt presente e accessibile
[✅/❌] sitemap.xml presente e accessibile
[✅/❌] Canonical URL su pagine chiave
[✅/❌] Meta title e description (globali)
[✅/❌] OG tags (og:title, og:description, og:image)
[✅/❌] Twitter/X card tags (twitter:card, twitter:title, twitter:image)
[✅/❌] Hreflang (se sito multilingua — IT/EN, x-default)
[✅/❌] Schema.org: Organization/WebSite su homepage
[✅/❌] Schema.org: page-specific (Article, HowTo, FAQ, ecc.)
[✅/❌] GA4 configurato ([measurement ID])
[⚠️/❌] Google Search Console: meta tag [presente/assente]
[🔲] Google Search Console: verifica completata
[🔲] GA4 collegato a GSC

### D. GEO / AI VISIBILITY
[✅/❌] llms.txt presente
[✅/❌] llms.txt spec-compliant (H1 + Markdown links assoluti)
[✅/❌] robots.txt non blocca AI crawlers (GPTBot, ClaudeBot, ecc.)
[🔲] Answer-first paragraphs nelle guide principali
[🔲] Contenuti citable (fonte, data, autore)

### E. LEGAL & GDPR
[✅/❌] Privacy Policy (/privacy)
[✅/❌] Termini e Condizioni (/termini)
[✅/❌] Cookie Policy (/cookie)
[✅/❌] Cookie Banner presente
[✅/❌] Consent Mode v2 (analytics denied by default)
[✅/❌] Revoca consenso accessibile dalla cookie policy
[✅/❌] Email privacy (privacy@dominio) presente
[🔲] Data Controller identificato nella Privacy Policy
[🔲] GDPR: base giuridica per ogni trattamento definita
[🔲] GDPR: data retention policy definita
[🔲] GDPR: DPO nominato (se applicabile)

### F. COMPANY INFO
[✅/❌] Footer: nome società/persona giuridica
[✅/❌] Footer: P.IVA / VAT number
[✅/❌] Footer: indirizzo sede
[✅/❌] Footer: email di contatto
[✅/❌] Footer: numero di telefono (se rilevante per il business)
[✅/❌] Footer: link legal (Privacy, Termini, Cookie)

### G. PERFORMANCE
[🔲] Lighthouse Performance ≥ 90
[🔲] LCP < 2.5s
[🔲] INP < 200ms
[🔲] CLS < 0.1
[✅/❌] Immagini ottimizzate (WebP/AVIF o next/image)
[✅/❌] Font ottimizzati (display: swap / next/font)
[🔲] Bundle JS < 200kB gzipped (first load)

### H. CONTENT & UX
[✅/❌] 404 page personalizzata
[✅/❌] Error page personalizzata (500)
[✅/❌] Favicon e app icons
[✅/❌] OG image per social sharing
[✅/❌] Copyright year nel footer aggiornato
[🔲] Homepage ottimizzata per keyword primaria
[🔲] Landing pages principali completate
[🔲] Competition analysis svolta
[🔲] Long-tail content strategy definita

### I. ACCESSIBILITÀ
[✅/❌] Attributo lang sull'elemento <html>
[✅/❌] Skip link ("Salta al contenuto") presente
[✅/❌] Tutti i tag <img> hanno attributo alt
[✅/❌] ARIA landmarks (nav, main, footer) etichettati
[✅/❌] Dichiarazione di accessibilità presente (/accessibility)
[✅/❌] :focus / :focus-visible definiti nel CSS
[🔲] Navigazione da tastiera verificata (Tab, Enter, Esc)
[🔲] Contrasto colori ≥ 4.5:1 (WCAG 2.1 AA)
[🔲] Heading hierarchy corretta (h1 → h2 → h3, no salti)
[🔲] Form con label associati correttamente
[🔲] Test con screen reader (NVDA / VoiceOver)
[🔲] Lighthouse Accessibility ≥ 90

### J. MONITORING
[✅/❌] Error monitoring (Sentry o equivalente)
[🔲] Uptime monitoring configurato (UptimeRobot, BetterStack, ecc.) — check **HTTP + DNS** da vantage
     esterno; senza una fonte indipendente non si distingue un outage da un problema di rete locale,
     né si sa quanto è durato
[🔲] Alert su downtime (email/Slack)
[🔲] Log di produzione accessibili
[🔲] Dashboard KPI / analytics review schedulata

### K. EMAIL TRANSAZIONALE
[✅/❌] SMTP configurato (credenziali in .env, non hardcoded)
[✅/❌] Form contatti: invio email funzionante (test manuale)
[✅/❌] SPF/DKIM per dominio mittente (non solo MX) — vedi §A, Step 3.2
[✅/❌] SPF copre **tutti** i mittenti: provider transazionale *e* provider delle caselle
[🔲] Email non finisce in spam (test con mail-tester.com)
[🔲] From: address reale e monitorato (non noreply generico)
[🔲] Reply-To configurato correttamente
[🔲] Test ricezione su Gmail, Outlook, Apple Mail — su Gmail aprire "Mostra originale": deve
     riportare `SPF: PASS` e `DKIM: PASS`

> Se l'autenticazione del prodotto è via **magic link / OTP via email**, SPF e DKIM salgono a **P0**:
> l'email non è una notifica, è il login. Una consegna in spam equivale a un utente che non entra —
> e che non lo segnala.

### L. FORM & ANTI-SPAM
[✅/❌] Validazione server-side su tutti i form
[✅/❌] Honeypot field o captcha presente
[✅/❌] Rate limiting sull'endpoint form
[✅/❌] Nessun campo nascosto che espone info server
[🔲] Test invio con dati malformati (SQL injection, XSS)
[🔲] Test invio multiplo rapido (rate limit verificato)

### M. LINK CHECKER
[✅/❌] Nessun link interno 404 nelle pagine principali
[✅/❌] Nessun link esterno rotto nelle pagine principali
[🔲] Verifica link nelle pagine secondarie (privacy, termini, ecc.)
[🔲] Anchor link (#id) funzionanti

### N. HREFLANG (solo siti multilingua)
[✅/❌] Tag hreflang su tutte le pagine
[✅/❌] Ogni pagina IT linka la corrispondente EN (e viceversa)
[✅/❌] x-default definito su tutte le pagine
[✅/❌] URL assoluti negli href hreflang (non relativi)
[🔲] Verifica con GSC o hreflang validator online

### O. BACKUP & RECOVERY
[🔲] Backup automatici configurati (file + database se presente)
[🔲] Frequenza backup adeguata (daily per siti attivi)
[🔲] Procedura di rollback documentata e testata
[🔲] Backup conservati off-site (non solo sul server)

### P. SEO ON-PAGE
[✅/❌] Meta title: lunghezza 50-60 caratteri, keyword primaria presente
[✅/❌] Meta description: lunghezza 120-160 caratteri, call-to-action implicita
[✅/❌] H1: presente e unico per pagina, contiene keyword principale
[✅/❌] og:image:width ≥ 1200 e og:image:height ≥ 630 dichiarati
[✅/❌] URL structure: lowercase, hyphen-separated, niente underscore né parametri nel canonico
[✅/❌] noindex/nofollow: solo su pagine NON destinate all'indice (grazie/admin/staging)
[🔲] Keyword primaria in H1, primo paragrafo e almeno un H2
[🔲] Thin content: pagine principali con ≥ 300 parole di testo body
[🔲] Heading hierarchy: H1→H2→H3 senza salti (da verificare su articoli/landing)
[🔲] Internal links: pagine chiave raggiungibili in ≤ 3 click dalla homepage
[🔲] URL leggibili: slug descrittivi (non /p=123 o /node/456)

### Q. IMAGE SEO
[✅/❌] Alt text su tutte le immagini <img> (contenuto, non decorativo)
[✅/❌] og:image presente con dimensioni ≥ 1200×630 px dichiarate
[✅/❌] Formato immagini moderno: WebP o AVIF per immagini content
[✅/❌] Lazy loading: attributo loading="lazy" o libreria equivalente
[🔲] Filename descrittivi (no image001.jpg, no IMG_1234.png)
[🔲] Immagini compresse: < 200 KB per immagine content (da verificare con PageSpeed)
[🔲] Responsive images: srcset e sizes corretti per schermi diversi
[🔲] Image sitemap (per siti news, e-commerce, portfolio ad alta densità visiva)

### R. E-E-A-T & TRUST SIGNALS
[✅/❌] About / Chi siamo page accessibile e indicizzabile
[✅/❌] Schema.org: contactPoint con email e/o telefono
[✅/❌] Schema.org: sameAs con profili social verificati (LinkedIn, X/Twitter, ecc.)
[✅/❌] Schema.org: address con indirizzo fisico (per Organization/LocalBusiness)
[✅/❌] ethicsPolicy o codice editoriale dichiarato (obbligatorio per news e org)
[🔲] Author bylines visibili (nome, ruolo/bio) su articoli/post
[🔲] Author pages indicizzabili (/author/[slug]) con bio e link profilo
[🔲] Data di pubblicazione e ultimo aggiornamento visibili sui contenuti
[🔲] Citazioni da fonti esterne autorevoli (verificare con GSC → Link)
[🔲] Wikipedia / Wikidata entry per brand consolidati
[🔲] Premi, certificazioni o menzioni stampa visibili (trust badge)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SCORE: [N✅ done] / [N totale] | [N❌ missing] | [N🔲 manual]

### 🔴 P0 — CRITICI (blocca lancio)
Elenca qui i ❌ in categorie A, B, E con impatto legale o di sicurezza

### 🟡 P1 — ALTA PRIORITÀ (rischio lancio)
Elenca qui i ❌ in categorie C (GSC, GA4), I (accessibilità base), J (monitoring), K (email), M (link interni rotti),
P (H1 assente, og:image < 1200×630), Q (immagini senza alt), R (About page assente)

### 🟢 P2 — OTTIMIZZAZIONE (post-lancio ok)
Elenca qui i ❌/⚠️ in categorie L (anti-spam), N (hreflang), H (copyright), C (Twitter card),
P (thin content, heading hierarchy), Q (WebP/AVIF, lazy loading), R (author bylines, date visibile)

### ⚪ P3 — BACKLOG (nice-to-have)
Elenca qui i 🔲 di content strategy, long-tail, competition, test screen reader, backup off-site, mail-tester,
Q (image sitemap, srcset), R (Wikipedia entry, citazioni esterne, premi)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### Step 5 — Salvataggio (opzionale)

Chiedi all'utente: "Vuoi che salvi il checklist in `GO-LIVE-CHECKLIST.md`?"

Se sì, salva nella root del progetto con:
- Header: nome progetto, URL, data, score
- Tutte le categorie con status corrente
- Sezione "Changelog" per tracciare i progressi nel tempo

---

## Logica priorità

### P0 — Critici (blocca lancio)
- ❌ HTTPS non funzionante
- ❌ Privacy Policy assente (obbligo legale GDPR)
- ❌ Cookie Banner assente se si usa analytics
- ❌ Consent Mode v2 non implementato con analytics
- ❌ CSP assente (rischio XSS)
- ❌ HSTS assente (downgrade attack)
- ❌ **SPF assente su un dominio che invia email** — e **sempre P0**, non P1, se l'autenticazione è via
  magic link / OTP: l'email è il login, in spam significa utenti che non entrano
- 🔴 **DMARC `p=quarantine`/`reject` con SPF o DKIM mancanti** — sta già bloccando le email del sito
- ❌ **Elenco sub-responsabili (art. 28 GDPR) che omette fornitori realmente in uso** — un'omissione pesa
  più di un errore: nasconde all'interessato chi tratta i suoi dati. Incrociare l'elenco della privacy
  con le dipendenze reali (email provider, error monitoring, hosting, servizi AI)

### P1 — Alta priorità
- ❌ Google Search Console non verificato
- ❌ robots.txt o sitemap.xml assenti
- ❌ 404 page mancante
- ❌ Uptime monitoring non configurato
- ❌ Footer senza P.IVA / dati legali
- ❌ Attributo lang assente su <html> (rompe screen reader)
- ❌ Immagini senza alt (barriera per non vedenti)
- ❌ Dichiarazione di accessibilità assente
- ❌ Email transazionale non funzionante (form contatti silenzioso)
- ❌ Link interni 404 nelle pagine principali

### P2 — Ottimizzazione (entro 2 settimane dal lancio)
- 🔲 Lighthouse < 90
- 🔲 GA4 non collegato a GSC
- ❌ llms.txt assente
- ❌ Schema.org mancante su pagine chiave
- 🔲 HSTS preload non submittato
- ❌ Anti-spam assente su form contatti
- ❌ Hreflang mancante (siti multilingua)
- ❌ Twitter/X card tags assenti
- ❌ Copyright year non aggiornato nel footer
- ❌ og:image:width/height < 1200×630 (P. SEO ON-PAGE)
- ❌ Immagini senza WebP/AVIF o senza lazy loading (Q. IMAGE SEO)
- ❌ Author bylines o date di pubblicazione assenti (R. E-E-A-T)
- ❌ sameAs profili social assenti in Schema.org (R. E-E-A-T)

### P3 — Backlog
- 🔲 Competition analysis
- 🔲 Long-tail content strategy
- 🔲 OG image personalizzate per pagina
- 🔲 Test accessibilità avanzato con screen reader (NVDA/VoiceOver)
- 🔲 Audit contrasto colori con strumento dedicato
- 🔲 Certificazione WCAG 2.1 AA (se PA o servizio pubblico)
- 🔲 Test email su Gmail, Outlook, Apple Mail (mail-tester.com)
- 🔲 Backup off-site configurato
- 🔲 Test link nelle pagine secondarie (privacy, accessibility, ecc.)
- 🔲 Image sitemap (Q. IMAGE SEO — per news, e-commerce, portfolio)
- 🔲 Responsive images srcset verificato (Q. IMAGE SEO)
- 🔲 Wikipedia / Wikidata entry (R. E-E-A-T — per brand consolidati)
- 🔲 Heading hierarchy audit sulle pagine principali (P. SEO ON-PAGE)
- 🔲 Thin content audit: pagine < 300 parole da espandere o noindex

---

## Adattamento per framework

### Next.js App Router
- Security headers → `next.config.ts` headers()
- Legal pages → `src/app/[slug]/page.tsx`
- Cookie banner → `src/components/`
- Consent → `src/lib/consent.ts` o similar
- robots.txt → `public/robots.txt` o `app/robots.ts`
- sitemap → `public/sitemap.xml` o `app/sitemap.ts`
- 404 → `src/app/not-found.tsx`
- Error → `src/app/error.tsx`
- GA4 → `src/app/layout.tsx` (script inline)

### Static (HTML/Jekyll/Hugo)
- Security headers → `_headers` (Netlify/Cloudflare) o nginx.conf
- Legal pages → `/privacy.html`, `/terms.html`, `/cookie.html`
- 404 → `404.html`

### Express/Node.js
- Security headers → `helmet()` middleware o headers manuali
- Legal pages → routes `/privacy`, `/terms`, `/cookie`

### Django
- Security headers → `settings.py` SECURE_* variables
- Legal pages → views/templates

---

## Note operative

- Esegui sempre lo scan codebase **prima** degli HTTP check: se il progetto è locale e non ancora deployato, salta gli HTTP check e segnala i 🔲 come "da verificare dopo deploy"
- Se il sito è in "coming soon" o maintenance mode, verifica anche le pagine dietro (con curl su path diretti)
- Per i check GDPR: non dare giudizi legali definitivi. Segnala se i componenti tecnici sono presenti; la revisione legale è sempre 🔲
- Non fare refactoring o correzioni automatiche: segnala solo, poi chiedi all'utente se vuole procedere con le correzioni

**Un check fallito non è un check superato.** Prima di marcare qualcosa come assente, verifica di aver
davvero ricevuto una risposta:

- `curl` che ritorna `000` o fallisce in ~1 ms non è "sito giù": è DNS/rete locale. Un host irraggiungibile
  consuma il timeout, non un millesimo di secondo
- `grep` su un body vuoto riporta "assente" per **qualsiasi** stringa e sembra una conferma. Controlla
  `-w '%{http_code} %{size_download}'` prima di interpretare un'assenza come un fatto
- Quando il risultato è sorprendente (sito che sembra down, header che spariscono), passa a
  **DNS-over-HTTPS** (`https://dns.google/resolve?name=…`) e a un vantage esterno
  (`https://r.jina.ai/https://…`) prima di scriverlo nel report

**Verifica gli identificatori esatti prima di raccomandarli.** Hostname SPF, nomi di selettori DKIM e
record dei provider sono facili da sbagliare a memoria, e un valore errato in un report porta chi legge a
pubblicare DNS rotti. Risolvili sempre con `dig` prima di consegnarli.

**Segnala anche le incoerenze tra fonti interne.** Dati che devono coincidere e non coincidono sono bug
reali, spesso invisibili a qualsiasi singolo check: P.IVA diversa tra footer e privacy, indirizzo diverso
tra termini e contatti, elenco fornitori della privacy che non corrisponde alle dipendenze del codice.

---

## Esempio di invocazione

```
/go-live                         → audit completo del progetto corrente
/go-live https://esempio.com     → audit con URL specificato
/go-live --save                  → audit + salva GO-LIVE-CHECKLIST.md
```
