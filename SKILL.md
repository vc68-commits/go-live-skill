---
name: go-live
description: "Go-live readiness agent for web apps and sites. Audits all launch-critical activities across 9 categories: infrastructure/DNS, security headers, SEO/GEO foundation, legal/GDPR, company info, performance, content/UX, monitoring. Produces a prioritized checklist with ✅/⚠️/❌/🔲 status. Run at any time to track launch readiness and identify blockers. Invoke when user says: go-live, go live, checklist lancio, pronto per produzione, launch checklist, or similar."
user-invokable: true
argument-hint: "[url]"
license: MIT
metadata:
  author: bollette.it
  version: "1.0.0"
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
```

**Content & UX**:
```bash
# 404 page
find . -name "not-found.tsx" -o -name "404.tsx" -o -name "404.html" | grep -v node_modules
# Error page
find . -name "error.tsx" -o -name "500.tsx" -o -name "500.html" | grep -v node_modules
# Favicon
find ./public -name "favicon*" -o -name "icon*" 2>/dev/null | head -10
```

**Monitoring**:
```bash
grep -r "sentry\|@sentry\|Sentry" . --include="*.ts" --include="*.tsx" --include="*.json" -l
grep -r "uptimerobot\|betterstack\|cronitor\|statuspage" . --include="*.ts" --include="*.tsx" -l
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
```

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
[🔲] Email dominio: MX configurato
[🔲] Email sicurezza: SPF, DKIM, DMARC

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
[🔲] Homepage ottimizzata per keyword primaria
[🔲] Landing pages principali completate
[🔲] Competition analysis svolta
[🔲] Long-tail content strategy definita

### I. MONITORING
[✅/❌] Error monitoring (Sentry o equivalente)
[🔲] Uptime monitoring configurato (UptimeRobot, BetterStack, ecc.)
[🔲] Alert su downtime (email/Slack)
[🔲] Log di produzione accessibili
[🔲] Dashboard KPI / analytics review schedulata

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SCORE: [N✅ done] / [N totale] | [N❌ missing] | [N🔲 manual]

### 🔴 P0 — CRITICI (blocca lancio)
Elenca qui i ❌ in categorie A, B, E con impatto legale o di sicurezza

### 🟡 P1 — ALTA PRIORITÀ (rischio lancio)
Elenca qui i ❌ in categoria C (GSC, GA4) e I (monitoring)

### 🟢 P2 — OTTIMIZZAZIONE (post-lancio ok)
Elenca qui i 🔲 e ⚠️ non bloccanti

### ⚪ P3 — BACKLOG (nice-to-have)
Elenca qui i 🔲 di content strategy, long-tail, competition
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

### P1 — Alta priorità
- ❌ Google Search Console non verificato
- ❌ robots.txt o sitemap.xml assenti
- ❌ 404 page mancante
- ❌ Uptime monitoring non configurato
- ❌ Footer senza P.IVA / dati legali

### P2 — Ottimizzazione (entro 2 settimane dal lancio)
- 🔲 Lighthouse < 90
- 🔲 GA4 non collegato a GSC
- ❌ llms.txt assente
- ❌ Schema.org mancante su pagine chiave
- 🔲 HSTS preload non submittato

### P3 — Backlog
- 🔲 Competition analysis
- 🔲 Long-tail content strategy
- 🔲 OG image personalizzate per pagina
- 🔲 Hreflang (se multilingua)

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

---

## Esempio di invocazione

```
/go-live                         → audit completo del progetto corrente
/go-live https://esempio.com     → audit con URL specificato
/go-live --save                  → audit + salva GO-LIVE-CHECKLIST.md
```
