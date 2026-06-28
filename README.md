Una skill invocabile in qualsiasi progetto che:

Legge il contesto (CLAUDE.md, package.json, config files) e rileva il framework
Scansiona il codebase (grep automatico per implementazioni)
Esegue HTTP check sul dominio live (headers, meta, robots)
Produce un report categorizzato con ✅ / ⚠️ / ❌ / 🔲 per ogni item
Salva GO-LIVE-CHECKLIST.md nella root del progetto per tracciare i progressi
9 categorie (dalla bollette.it experience):

#	Categoria	Check automatici	Check manuali
A	Infrastruttura & DNS	SSL/HTTPS, redirect	DNS, MX, DKIM/SPF
B	Sicurezza	HSTS, CSP, X-Frame, nosniff	Rate limiting, pentest
C	SEO Foundation	robots.txt, sitemap, canonical, schema, GA4, GSC meta	GSC verified, GA4↔GSC link
D	GEO / AI	llms.txt spec, AI-friendly markup	AI crawlers test
E	Legal & GDPR	Privacy/Termini/Cookie pages, banner, consent mode	DPO, DPIA, retention policy
F	Company info	Footer P.IVA, indirizzo, legal links	—
G	Performance	Bundle size, immagini ottimizzate	Lighthouse, CWV
H	Content & UX	404, OG tags, favicon, error pages	Landing KW, competitor gap
I	Monitoring	Sentry/error, uptime config	Alert, log review
Output: priorità P0 (blocca lancio) → P1 → P2 → P3

usalo in qualsiasi progetto con /go-live o /go-live https://esempio.com
