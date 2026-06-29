---
name: go-live
description: "Go-live readiness agent for web apps and sites. Audits all launch-critical activities across 15 categories: infrastructure/DNS, security, SEO, GEO/AI, legal/GDPR, company info, performance, content/UX, accessibility, monitoring, email, forms/anti-spam, link checker, hreflang, backup. Produces a prioritized checklist with ✅/⚠️/❌/🔲 status. Run at any time to track launch readiness and identify blockers. Invoke when user says: go-live, go live, checklist lancio, pronto per produzione, launch checklist, or similar."
user-invokable: true
argument-hint: "[url]"
license: MIT
metadata:
  author: bollette.it
  version: "1.2.0"
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
[🔲] Uptime monitoring configurato (UptimeRobot, BetterStack, ecc.)
[🔲] Alert su downtime (email/Slack)
[🔲] Log di produzione accessibili
[🔲] Dashboard KPI / analytics review schedulata

### K. EMAIL TRANSAZIONALE
[✅/❌] SMTP configurato (credenziali in .env, non hardcoded)
[✅/❌] Form contatti: invio email funzionante (test manuale)
[✅/❌] SPF/DKIM per dominio mittente (non solo MX)
[🔲] Email non finisce in spam (test con mail-tester.com)
[🔲] From: address reale e monitorato (non noreply generico)
[🔲] Reply-To configurato correttamente
[🔲] Test ricezione su Gmail, Outlook, Apple Mail

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

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SCORE: [N✅ done] / [N totale] | [N❌ missing] | [N🔲 manual]

### 🔴 P0 — CRITICI (blocca lancio)
Elenca qui i ❌ in categorie A, B, E con impatto legale o di sicurezza

### 🟡 P1 — ALTA PRIORITÀ (rischio lancio)
Elenca qui i ❌ in categorie C (GSC, GA4), I (accessibilità base), J (monitoring), K (email), M (link interni rotti)

### 🟢 P2 — OTTIMIZZAZIONE (post-lancio ok)
Elenca qui i ❌/⚠️ in categorie L (anti-spam), N (hreflang), H (copyright), C (Twitter card) e i 🔲 non bloccanti

### ⚪ P3 — BACKLOG (nice-to-have)
Elenca qui i 🔲 di content strategy, long-tail, competition, test screen reader, backup off-site, mail-tester
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
