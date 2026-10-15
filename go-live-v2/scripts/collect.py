#!/usr/bin/env python3
"""go-live collect: raccoglie in modo DETERMINISTICO i fatti per la checklist go-live (categorie A-S).

Solo libreria standard. Solo richieste in lettura, con ritardo tra richieste (cortese).
Uso:  collect.py --config go-live.toml [--url https://dominio] [--out DIR] [--md] [--no-history]
Esce con codice 0; il verdetto sta nel JSON/Markdown, non nel codice di uscita.
"""
import argparse
import datetime as dt
import fnmatch
import glob
import json
import os
import random
import re
import sys
import time
import tomllib
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from golive_lib import (CTX, Http, doh, doh_values, host_of, html_to_text, image_size, parse_html,  # noqa: E402
                        piva_valid, same_site, tls_info, txt_join)

VERSION = "2.3.0"

CATS = {
    "A": "INFRASTRUTTURA & DNS", "B": "SICUREZZA", "C": "SEO FOUNDATION", "D": "GEO / AI VISIBILITY",
    "E": "LEGAL & GDPR", "F": "COMPANY INFO", "G": "PERFORMANCE", "H": "CONTENT & UX",
    "I": "ACCESSIBILITÀ", "J": "MONITORING", "K": "EMAIL TRANSAZIONALE", "L": "FORM & ANTI-SPAM",
    "M": "LINK CHECKER", "N": "HREFLANG", "O": "BACKUP & RECOVERY", "P": "SEO ON-PAGE",
    "Q": "IMAGE SEO", "R": "E-E-A-T & TRUST SIGNALS", "S": "COERENZA TRA FONTI (dichiarato vs reale)",
    "X": "AGENT READINESS — Ora `ax` (passo OPZIONALE, servizio esterno)",
    "Y": "AGENT READINESS — Is Agentic (Vercel/Ora, passo OPZIONALE, servizio esterno)",
    "Z": "ERRORI INTERNI DEL RACCOGLITORE (sezioni non eseguite)",
}
ICON = {"ok": "✅", "warn": "⚠️", "fail": "❌", "manual": "🔲", "na": "➖"}

DEFAULTS = {
    "name": None, "domain": None, "url": None, "language": "it", "multilingual": False,
    "crawl": {"delay_s": 1.0, "max_pages": 30, "max_link_checks": 60, "max_external_checks": 15,
              "sample_paths": []},
    "email": {"sends_email": True, "auth_via_email": False, "providers": [], "dkim_selectors": []},
    "legal": {"privacy_paths": ["/privacy", "/privacy-policy", "/informativa-privacy"],
              "terms_paths": ["/termini", "/termini-e-condizioni", "/terms", "/condizioni"],
              "cookie_paths": ["/cookie", "/cookie-policy"],
              "accessibility_paths": ["/accessibilita", "/accessibility", "/dichiarazione-accessibilita"],
              "about_paths": ["/chi-siamo", "/about", "/about-us", "/perche-noi", "/azienda", "/team"],
              "expected_subprocessors": [], "vat": None},
    # agent: markdown = None (auto: i controlli D05-D07/D11 si applicano solo se la home serve Markdown),
    #        True (il sito dichiara di supportarlo: l'assenza è un fallimento), False (non applicabile)
    "agent": {"markdown": None, "contact_paths": ["/contact", "/contatti", "/contattaci", "/contact-us"],
              "trust_min_chars": 500,
              # passo opzionale (--ax): CLI "ax" di Ora, INVIA IL DOMINIO a ora.ai. Versione fissata per evitare sorprese.
              "isagentic": False, "isagentic_min_score": 90, "isagentic_max_age_h": 24,
              "ax": False, "ax_package": "ax@0.10.1", "ax_min_score": None, "ax_force": False, "ax_top": 6},
    "noindex_ok": ["/admin", "/app", "/auth", "/api", "/onboarding", "/login", "/grazie", "/thank-you"],
    "ignore": {"checks": []},
    "browser": {"enabled": False, "pages": 5, "mobile": True, "lighthouse": True, "python": ""},
    "notify": {"mode": "changes", "telegram_env": "~/.config/go-live/telegram.env", "cert_days_warn": 30},
}
SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# fornitore -> (suffissi di dominio, nome mostrato, alias da cercare nella privacy)
VENDORS = [
    (["google-analytics.com", "googletagmanager.com", "analytics.google.com", "googleadservices.com",
      "doubleclick.net", "googlesyndication.com"], "Google (Analytics/Tag Manager)", ["Google"]),
    (["gstatic.com", "google.com", "recaptcha.net"], "Google (servizi/reCAPTCHA)", ["Google"]),
    (["fonts.googleapis.com", "fonts.gstatic.com"], "Google Fonts", ["Google"]),
    (["googleapis.com"], "Google APIs", ["Google"]),
    (["facebook.net", "facebook.com", "fbcdn.net", "connect.facebook.net"], "Meta", ["Meta", "Facebook"]),
    (["sentry.io"], "Sentry", ["Sentry"]),
    (["cloudflare.com", "cloudflareinsights.com", "cdnjs.cloudflare.com", "challenges.cloudflare.com"],
     "Cloudflare", ["Cloudflare"]),
    (["stripe.com", "stripe.network"], "Stripe", ["Stripe"]),
    (["hotjar.com", "hotjar.io"], "Hotjar", ["Hotjar"]),
    (["clarity.ms"], "Microsoft Clarity", ["Clarity", "Microsoft"]),
    (["linkedin.com", "licdn.com"], "LinkedIn", ["LinkedIn"]),
    (["tiktok.com"], "TikTok", ["TikTok"]),
    (["youtube.com", "youtube-nocookie.com", "ytimg.com"], "YouTube", ["YouTube", "Google"]),
    (["vimeo.com", "vimeocdn.com"], "Vimeo", ["Vimeo"]),
    (["intercom.io", "intercomcdn.com"], "Intercom", ["Intercom"]),
    (["crisp.chat"], "Crisp", ["Crisp"]),
    (["hubspot.com", "hs-scripts.com", "hsforms.net"], "HubSpot", ["HubSpot"]),
    (["mailchimp.com", "list-manage.com"], "Mailchimp", ["Mailchimp"]),
    (["jsdelivr.net"], "jsDelivr", ["jsDelivr"]),
    (["unpkg.com"], "unpkg", ["unpkg"]),
    (["typekit.net", "adobe.com"], "Adobe Fonts", ["Adobe"]),
    (["vercel.app", "vercel-insights.com", "vercel-scripts.com", "vercel.com"], "Vercel", ["Vercel"]),
    (["plausible.io"], "Plausible", ["Plausible"]),
    (["posthog.com"], "PostHog", ["PostHog"]),
    (["segment.com", "segment.io"], "Segment", ["Segment"]),
    (["paypal.com", "paypalobjects.com"], "PayPal", ["PayPal"]),
    (["mapbox.com"], "Mapbox", ["Mapbox"]),
    (["supabase.co", "supabase.com"], "Supabase", ["Supabase"]),
    (["resend.com"], "Resend", ["Resend"]),
    (["amazonaws.com", "cloudfront.net", "amazonses.com"], "Amazon (AWS)", ["Amazon", "AWS"]),
    (["algolia.net", "algolia.com"], "Algolia", ["Algolia"]),
    (["calendly.com"], "Calendly", ["Calendly"]),
    (["trustpilot.com"], "Trustpilot", ["Trustpilot"]),
    (["klaviyo.com"], "Klaviyo", ["Klaviyo"]),
    (["onesignal.com"], "OneSignal", ["OneSignal"]),
    (["iubenda.com"], "Iubenda", ["Iubenda"]),
    (["cookiebot.com"], "Cookiebot", ["Cookiebot"]),
]

# provider email -> (nome, include SPF, selettori DKIM probabili, token MX, alias privacy)
MAIL_PROVIDERS = {
    "resend": ("Resend", ["resend"], ["resend"], [], ["Resend"]),
    "amazonses": ("Amazon SES", ["amazonses.com"], [], [], ["Amazon SES", "SES"]),
    "qboxmail": ("Qboxmail", ["qboxmail.com"], [], ["qboxmail.com"], ["Qboxmail"]),
    "google": ("Google Workspace", ["_spf.google.com", "google.com"], ["google"], ["google.com", "googlemail.com"],
               ["Google Workspace", "Gmail", "Google"]),
    "microsoft": ("Microsoft 365", ["spf.protection.outlook.com"], ["selector1", "selector2"],
                  ["mail.protection.outlook.com"], ["Microsoft", "Outlook"]),
    "sendgrid": ("SendGrid", ["sendgrid.net"], ["s1", "s2"], [], ["SendGrid", "Twilio"]),
    "mailgun": ("Mailgun", ["mailgun.org"], ["k1", "mailo", "smtp"], [], ["Mailgun"]),
    "postmark": ("Postmark", ["spf.mtasv.net"], ["pm", "20230601"], [], ["Postmark"]),
    "brevo": ("Brevo", ["spf.brevo.com", "sendinblue.com"], ["brevo1", "mail"], [], ["Brevo", "Sendinblue"]),
    "mailchimp": ("Mailchimp/Mandrill", ["mandrillapp.com", "servers.mcsv.net"], ["k1", "mte1"], [], ["Mailchimp", "Mandrill"]),
}
COMMON_DKIM = ["default", "google", "selector1", "selector2", "k1", "k2", "mail", "smtp", "s1", "s2", "resend",
               "pm", "mandrill", "dkim", "zoho", "mxvault", "brevo1", "protonmail"]
AI_BOTS = ["GPTBot", "OAI-SearchBot", "ChatGPT-User", "ClaudeBot", "Claude-Web", "anthropic-ai", "PerplexityBot",
           "Google-Extended", "Applebot-Extended", "CCBot", "Bytespider", "Amazonbot", "meta-externalagent"]
KEY_BOTS = ["GPTBot", "OAI-SearchBot", "ClaudeBot", "PerplexityBot", "Google-Extended"]
ANALYTICS_COOKIES = re.compile(r"^(_ga|_gid|_gat|_gcl|_fbp|_fbc|_hj|__utm|ajs_|mp_|_clck|_clsk|_pk_)", re.I)

# priorità: (priorità se fail, priorità se warn)
PRIO = {
    "A01": ("P0", "P1"), "A06": ("P1", "P2"), "A07": ("P1", "P2"), "B01": ("P0", "P2"), "B02": ("P0", "P2"),
    "C01": ("P1", "P2"), "C02": ("P1", "P2"), "C11": ("P1", "P2"), "E01": ("P0", "P1"), "E02": ("P1", "P2"),
    "E03": ("P1", "P2"), "E04": ("P0", "P1"), "E05": ("P0", "P1"), "E06": ("P0", "P1"), "F02": ("P1", "P2"),
    "H01": ("P1", "P2"), "I01": ("P1", "P2"), "I03": ("P1", "P2"), "I05": ("P1", "P2"), "J01": ("P1", "P2"),
    "K02": ("P1", "P1"), "M01": ("P1", "P2"), "P03": ("P1", "P2"), "Q01": ("P1", "P2"), "R01": ("P1", "P2"),
    "S01": ("P0", "P1"), "S03": ("P1", "P1"), "S04": ("P1", "P2"),
    "E04": ("P0", "P1"), "E04b": ("P1", "P1"), "E06b": ("P0", "P1"), "E06c": ("P0", "P1"), "E06d": ("P0", "P1"),
    "D05": ("P2", "P2"), "D06": ("P2", "P2"), "D07": ("P3", "P3"), "D08": ("P2", "P2"), "D10": ("P2", "P2"),
    "D11": ("P1", "P1"), "D12": ("P3", "P3"),
    "I11": ("P1", "P2"), "I12": ("P1", "P2"), "I13": ("P1", "P2"), "H09": ("P1", "P2"),
    "G07m": ("P1", "P2"), "G07d": ("P1", "P2"), "I15m": ("P1", "P2"), "I15d": ("P1", "P2"),
}


# =========================================================================== modello risultati
class Audit:
    def __init__(self, cfg):
        self.cfg = cfg
        self.checks = []
        self.facts = {}
        self.notes = []

    def add(self, cid, title, status, evidence="", prio=None):
        assert status in ICON, status
        self.checks.append({"id": cid, "cat": cid[0], "title": title, "status": status,
                            "evidence": str(evidence)[:900], "prio": prio})

    def get(self, cid):
        for c in self.checks:
            if c["id"] == cid:
                return c
        return None


def short(s, n=140):
    s = re.sub(r"\s+", " ", str(s)).strip()
    return s if len(s) <= n else s[: n - 1] + "…"


def load_config(path, url_arg):
    cfg = json.loads(json.dumps(DEFAULTS))
    if path:
        with open(path, "rb") as f:
            user = tomllib.load(f)
        for k, v in user.items():
            if isinstance(v, dict) and isinstance(cfg.get(k), dict):
                cfg[k].update(v)
            else:
                cfg[k] = v
    if url_arg:
        cfg["url"] = url_arg
    if not cfg.get("url") and cfg.get("domain"):
        cfg["url"] = "https://" + cfg["domain"]
    if not cfg.get("url"):
        sys.exit("Serve 'url' o 'domain' nella configurazione, oppure --url.")
    u = urllib.parse.urlsplit(cfg["url"])
    cfg["domain"] = (cfg.get("domain") or u.hostname).removeprefix("www.")
    cfg["url"] = f"{u.scheme or 'https'}://{u.hostname}".rstrip("/")
    cfg["name"] = cfg.get("name") or cfg["domain"]
    return cfg


# =========================================================================== raccolta
class Collector:
    def __init__(self, cfg):
        self.cfg = cfg
        self.a = Audit(cfg)
        self.http = Http(delay=cfg["crawl"]["delay_s"])
        self.base = cfg["url"]
        self.domain = cfg["domain"]
        self.pages = {}
        self.t0 = time.time()
        self.home = None
        self.third_hosts = set()
        self.vendors_detected = {}
        self.js_texts = {}
        self.css_texts = {}
        self.legal_text = {}

    # ---------------------------------------------------------------- utilità
    def url(self, path):
        return urllib.parse.urljoin(self.base + "/", path.lstrip("/"))

    def norm(self, u):
        """URL canonico per deduplicare: senza frammento, radice = '/', senza slash finale altrove."""
        sp = urllib.parse.urlsplit(u)
        path = sp.path or "/"
        if path != "/":
            path = path.rstrip("/")
        return urllib.parse.urlunsplit((sp.scheme, sp.netloc.lower(), path, sp.query, ""))

    def page(self, url, maxbytes=2_500_000):
        if url in self.pages:
            return self.pages[url]
        res = self.http.fetch(url, maxbytes=maxbytes)
        html = Http.text(res) if res["ok"] else ""
        p = parse_html(html) if html and "html" in res["headers"].get("content-type", "html").lower() else None
        self.pages[url] = {"res": res, "html": html, "p": p, "url": url}
        return self.pages[url]

    def first_ok(self, paths):
        for pth in paths:
            pg = self.page(self.url(pth))
            if pg["res"]["ok"] and pg["res"]["status"] == 200 and len(pg["html"]) > 500:
                return pth, pg
        return None, None

    def asset(self, url, maxbytes=1_500_000):
        time.sleep(0.2)
        return self.http.fetch(url, polite=False, maxbytes=maxbytes)

    # ---------------------------------------------------------------- A: infrastruttura e DNS
    def run_A(self):
        a, d = self.a, self.domain
        home = self.page(self.base + "/")
        self.home = home
        r = home["res"]
        ti = tls_info(d)
        self.a.facts["tls"] = ti
        if r["ok"] and r["status"] == 200 and ti.get("ok"):
            days = ti["days_left"]
            st = "ok" if days >= 30 else ("warn" if days >= 14 else "fail")
            covers = any(s == d or (s.startswith("*.") and d.endswith(s[1:])) for s in ti["san"])
            if not covers:
                st = "fail"
            a.add("A01", "HTTPS attivo e certificato valido", st,
                  f"HTTP {r['status']}; {ti['tls']}; emittente {ti['issuer']}; scade tra {days} giorni "
                  f"({ti['not_after']}); copre {d}: {'sì' if covers else 'NO'}")
        else:
            a.add("A01", "HTTPS attivo e certificato valido", "fail",
                  f"HTTP {r.get('status')}; errore: {r.get('error') or ti.get('error')}")
        h = self.http.fetch("http://" + d + "/", follow=False)
        loc = h["headers"].get("location", "")
        if h["ok"] and h["status"] in (301, 308) and loc.startswith("https://"):
            a.add("A02", "Redirect HTTP → HTTPS (301/308)", "ok", f"{h['status']} → {loc}")
        elif h["ok"] and h["status"] in (302, 307) and loc.startswith("https://"):
            a.add("A02", "Redirect HTTP → HTTPS (301/308)", "warn", f"{h['status']} temporaneo → {loc}")
        else:
            a.add("A02", "Redirect HTTP → HTTPS (301/308)", "fail" if h["ok"] else "manual",
                  f"status {h.get('status')} location '{loc}' err {h.get('error')}")
        www = self.http.fetch(f"https://www.{d}/", follow=False)
        if not www["ok"]:
            a.add("A03", "Redirect www ↔ apex", "na", f"www.{d} non risponde ({short(www['error'], 80)})")
        elif www["status"] in (301, 308) and d in www["headers"].get("location", ""):
            a.add("A03", "Redirect www ↔ apex", "ok", f"{www['status']} → {www['headers'].get('location')}")
        elif www["status"] == 200:
            a.add("A03", "Redirect www ↔ apex", "warn", "www e apex rispondono entrambi 200: contenuto duplicato")
        else:
            a.add("A03", "Redirect www ↔ apex", "warn", f"www: status {www['status']}")
        rA, vA = doh_values(d, "A")
        a.add("A04", "DNS: record A/AAAA risolve", "ok" if vA else ("manual" if not rA["ok"] else "fail"),
              f"A {', '.join(vA[:4]) or '—'} (stato DNS {rA['status']}; {rA['error'] or 'ok'})")
        self.facts_dns_email()

    def _spf_lookups(self, spf, depth=0, seen=None):
        """Conta i termini che causano lookup DNS (limite 10); segnala include non risolvibili."""
        seen = seen if seen is not None else set()
        n, broken = 0, []
        for term in spf.split()[1:]:
            t = term.lstrip("+-~?")
            if t.startswith("include:") or t.startswith("redirect="):
                tgt = t.split(":", 1)[-1] if t.startswith("include:") else t.split("=", 1)[1]
                n += 1
                if tgt in seen or depth > 5:
                    continue
                seen.add(tgt)
                _, vals = doh_values(tgt, "TXT")
                recs = [txt_join(v) for v in vals if "v=spf1" in v.lower()]
                if not recs:
                    broken.append(tgt)
                else:
                    sub_n, sub_b = self._spf_lookups(recs[0], depth + 1, seen)
                    n += sub_n
                    broken += sub_b
            elif t.split(":")[0].split("/")[0] in ("a", "mx", "ptr", "exists"):
                n += 1
        return n, broken

    def facts_dns_email(self):
        a, d, em = self.a, self.domain, self.cfg["email"]
        sends = em["sends_email"]
        crit = "P0" if (em["auth_via_email"]) else None
        rM, vM = doh_values(d, "MX")
        mx_hosts = [m.split()[-1].rstrip(".").lower() for m in vM]
        a.facts["mx"] = mx_hosts
        a.add("A05", "MX configurato (se il dominio riceve posta)", "ok" if vM else ("manual" if not rM["ok"] else "warn"),
              f"MX: {', '.join(vM) or '—'}")
        rT, vT = doh_values(d, "TXT")
        txts = [txt_join(v) for v in vT]
        spfs = [t for t in txts if t.lower().startswith("v=spf1")]
        a.facts["spf"] = spfs
        if not rT["ok"]:
            a.add("A06", "SPF: presente, singolo, ≤10 lookup, include validi", "manual",
                  f"[QUERY DNS FALLITA {rT['error']}] non concludere nulla", crit)
        elif not spfs:
            a.add("A06", "SPF: presente, singolo, ≤10 lookup, include validi",
                  "fail" if (sends or mx_hosts) else "warn", "nessun record v=spf1 sull'apex", crit)
        elif len(spfs) > 1:
            a.add("A06", "SPF: presente, singolo, ≤10 lookup, include validi", "fail",
                  f"{len(spfs)} record v=spf1: si invalidano (permerror)", crit)
        else:
            spf = spfs[0]
            n, broken = self._spf_lookups(spf)
            st, notes = "ok", []
            if re.search(r"\s\+?all\b", spf) and not re.search(r"[-~?]all", spf):
                st, notes = "fail", ["+all autorizza chiunque"]
            elif "?all" in spf or not re.search(r"[-~]all", spf):
                st, notes = "warn", ["senza policy effettiva (?all o assente)"]
            if n > 10:
                st, notes = "fail", notes + [f"{n} lookup > 10: permerror"]
            if broken:
                st, notes = "fail", notes + [f"include non risolvibili: {', '.join(broken)}"]
            a.add("A06", "SPF: presente, singolo, ≤10 lookup, include validi", st,
                  f"{spf} | lookup stimati {n} {'; '.join(notes)}", crit if st == "fail" else None)
        rD, vD = doh_values("_dmarc." + d, "TXT")
        dm = [txt_join(v) for v in vD if "dmarc1" in v.lower()]
        a.facts["dmarc"] = dm
        if not rD["ok"]:
            a.add("A07", "DMARC presente con rua=", "manual", f"[QUERY DNS FALLITA {rD['error']}]")
        elif not dm:
            a.add("A07", "DMARC presente con rua=", "fail" if (sends or mx_hosts) else "warn", "nessun record _dmarc")
        else:
            rec = dm[0]
            pol = (re.search(r"\bp=(\w+)", rec) or [None, "?"])[1].lower()
            rua = re.search(r"rua=([^;]+)", rec)
            spf_ok = bool(spfs)
            if pol in ("quarantine", "reject") and not spf_ok:
                a.add("A07", "DMARC presente con rua=", "fail", f"{rec} — policy attiva ma SPF assente: BLOCCA le email del sito", "P0")
            elif pol == "none" and not rua:
                a.add("A07", "DMARC presente con rua=", "warn", f"{rec} — p=none senza rua: non protegge né raccoglie report")
            elif pol == "none":
                a.add("A07", "DMARC presente con rua=", "warn",
                      f"{rec} — p=none: solo monitoraggio; passare a quarantine dopo 2-4 settimane di report puliti. "
                      "Verificare che la casella rua esista.")
            else:
                a.add("A07", "DMARC presente con rua=", "ok" if rua else "warn", rec)
        sel = list(dict.fromkeys(em["dkim_selectors"] + COMMON_DKIM))
        found = []
        for s in sel:
            r, _ = doh_values(f"{s}._domainkey.{d}", "TXT")
            hit = [x for x in r["answers"] if x["type"] in (5, 16) and (x["type"] == 5 or "p=" in x["data"] or "dkim1" in x["data"].lower())]
            if hit:
                found.append(f"{s} ({'CNAME' if hit[0]['type'] == 5 else 'TXT'})")
        a.facts["dkim_found"] = found
        if found:
            a.add("A08", "DKIM: selettori pubblicati", "ok", "trovati: " + ", ".join(found))
        else:
            a.add("A08", "DKIM: selettori pubblicati", "manual",
                  f"nessuno dei {len(sel)} selettori provati. I selettori non sono indovinabili: l'assenza NON prova che "
                  "manchi; indicarli in [email].dkim_selectors o verificarli nella console del provider")
        rC, vC = doh_values(d, "CAA")
        a.add("A09", "CAA: autorità di certificazione autorizzate", "ok" if vC else "warn",
              f"CAA: {', '.join(vC) or 'assente (consigliato, non bloccante)'}")
        rS, vS = doh_values(d, "DS")
        a.add("A10", "DNSSEC", "na", "DS presente" if vS else "nessun DS: zona non firmata (non è un errore)")

    # ---------------------------------------------------------------- B: sicurezza
    def run_B(self):
        a, r = self.a, self.home["res"]
        h = r["headers"]
        if not r["ok"]:
            a.add("B01", "Header di sicurezza", "manual", "homepage non raggiungibile")
            return
        hsts = h.get("strict-transport-security", "")
        m = re.search(r"max-age=(\d+)", hsts)
        if not hsts:
            a.add("B01", "HSTS (Strict-Transport-Security)", "fail", "assente")
        else:
            age = int(m.group(1)) if m else 0
            st = "ok" if age >= 15552000 else "warn"
            a.add("B01", "HSTS (Strict-Transport-Security)", st,
                  f"{hsts}" + ("" if age >= 15552000 else " — max-age < 6 mesi") +
                  ("" if "includesubdomains" in hsts.lower() else " | senza includeSubDomains") +
                  (" | preload" if "preload" in hsts.lower() else " | senza preload"))
        csp = h.get("content-security-policy", "")
        self.a.facts["csp"] = csp
        if not csp:
            a.add("B02", "CSP (Content-Security-Policy)", "fail", "assente (rischio XSS)")
        else:
            dirs = {}
            for part in csp.split(";"):
                bits = part.strip().split()
                if bits:
                    dirs[bits[0].lower()] = bits[1:]
            issues = []
            script = dirs.get("script-src", dirs.get("default-src", []))
            if "'unsafe-inline'" in script and not any(x.startswith("'nonce-") or x.startswith("'sha") for x in script):
                issues.append("script-src con 'unsafe-inline' (senza nonce/hash): riduce molto la protezione XSS")
            if "'unsafe-eval'" in script:
                issues.append("script-src con 'unsafe-eval'")
            if "*" in script:
                issues.append("script-src con wildcard *")
            for need in ("object-src", "base-uri", "frame-ancestors"):
                if need not in dirs:
                    issues.append(f"manca {need}")
            a.add("B02", "CSP (Content-Security-Policy)", "warn" if issues else "ok",
                  ("; ".join(issues) or "CSP presente e senza criticità note") + f" | direttive: {', '.join(dirs)}")
        xfo = h.get("x-frame-options", "")
        fa = "frame-ancestors" in csp
        a.add("B03", "Protezione clickjacking (X-Frame-Options / frame-ancestors)",
              "ok" if (xfo.upper() in ("DENY", "SAMEORIGIN") or fa) else "fail",
              f"X-Frame-Options: {xfo or '—'}; frame-ancestors in CSP: {'sì' if fa else 'no'}")
        a.add("B04", "X-Content-Type-Options: nosniff", "ok" if h.get("x-content-type-options", "").lower() == "nosniff" else "fail",
              h.get("x-content-type-options", "assente"))
        a.add("B05", "Referrer-Policy", "ok" if h.get("referrer-policy") else "fail", h.get("referrer-policy", "assente"))
        a.add("B06", "Permissions-Policy", "ok" if h.get("permissions-policy") else "warn",
              short(h.get("permissions-policy", "assente")))
        leak = []
        if h.get("x-powered-by"):
            leak.append("x-powered-by: " + h["x-powered-by"])
        if re.search(r"\d+\.\d+", h.get("server", "")):
            leak.append("server: " + h["server"])
        a.add("B07", "Nessuna fuga di versioni (X-Powered-By / Server)", "warn" if leak else "ok", "; ".join(leak) or "nessuna")
        bad = []
        for c in r["set_cookie"]:
            name = c.split("=")[0].strip()
            flags = c.lower()
            miss = [f for f, ok in (("Secure", "secure" in flags), ("HttpOnly", "httponly" in flags),
                                    ("SameSite", "samesite" in flags)) if not ok]
            if miss:
                bad.append(f"{name} senza {'/'.join(miss)}")
        a.add("B08", "Cookie: flag Secure/HttpOnly/SameSite", "na" if not r["set_cookie"] else ("warn" if bad else "ok"),
              "; ".join(bad) or (f"{len(r['set_cookie'])} cookie sulla prima risposta, flag corretti" if r["set_cookie"]
                                  else "nessun cookie impostato sulla prima risposta"))
        mixed = [x for x in self._resources(self.home["p"]) if x.startswith("http://")]
        a.add("B09", "Nessun contenuto misto (http:// in pagina HTTPS)", "fail" if mixed else "ok", ", ".join(mixed[:5]) or "nessuno")
        sec = self.http.fetch(self.url("/.well-known/security.txt"))
        a.add("B10", "security.txt (/.well-known/)", "ok" if sec["ok"] and sec["status"] == 200 and b"Contact" in sec["body"] else "warn",
              f"status {sec['status']}" + ("" if sec["status"] == 200 else " — consigliato per la segnalazione di vulnerabilità"))
        a.add("B11", "Rate limiting API sensibili", "manual", "non verificabile dall'esterno senza test di carico")

    # ---------------------------------------------------------------- risorse / domini terzi
    def _resources(self, p):
        out = []
        if not p:
            return out
        out += [s.get("src", "") for s in p.scripts if s.get("src")]
        out += [l.get("href", "") for l in p.links if l.get("href") and any(
            k in l.get("rel", "").lower() for k in ("stylesheet", "preload", "preconnect", "dns-prefetch", "icon", "prefetch"))]
        out += [i.get("src", "") for i in p.imgs if i.get("src")]
        out += [f.get("src", "") for f in p.iframes if f.get("src")]
        return [urllib.parse.urljoin(self.base + "/", x) for x in out if x and not x.startswith(("data:", "blob:", "#"))]

    def collect_third_parties(self):
        hosts = set()
        for pg in self.pages.values():
            for u in self._resources(pg["p"]):
                hosts.add(host_of(u))
        csp = self.a.facts.get("csp", "")
        for tok in re.findall(r"(?:https?://)?(\*?\.?[a-z0-9.-]+\.[a-z]{2,})(?::\d+)?", csp):
            hosts.add(tok.lstrip("*."))
        first = {h for h in hosts if h and same_site(h, self.domain)}
        self.third_hosts = {h for h in hosts if h and h not in first and "." in h}
        for hosts_suffix, name, aliases in VENDORS:
            matched = sorted(h for h in self.third_hosts if any(h == s or h.endswith("." + s) for s in hosts_suffix))
            if matched:
                self.vendors_detected.setdefault(name, {"aliases": aliases, "hosts": [], "why": "dominio terzo in pagina/CSP"})["hosts"] += matched
        h = self.home["res"]["headers"] if self.home else {}
        if h.get("server", "").lower() == "cloudflare" or "cf-ray" in h:
            self.vendors_detected.setdefault("Cloudflare", {"aliases": ["Cloudflare"], "hosts": [], "why": "header server/cf-ray"})
        known = {s for hs, _, _ in VENDORS for s in hs}
        self.a.facts["third_party_unclassified"] = sorted(
            x for x in self.third_hosts if not any(x == s or x.endswith("." + s) for s in known))

    # ---------------------------------------------------------------- C, D: SEO foundation e GEO
    def run_C_D(self):
        a = self.a
        rb = self.page(self.url("/robots.txt"))
        txt = rb["html"] if rb["res"]["ok"] and rb["res"]["status"] == 200 else ""
        self.robots = txt
        sitemaps = re.findall(r"(?im)^sitemap:\s*(\S+)", txt)
        if not txt or "user-agent" not in txt.lower():
            a.add("C01", "robots.txt presente e valido", "fail", f"status {rb['res']['status']} / senza User-agent")
        else:
            groups, cur = {}, []
            for line in txt.splitlines():
                line = line.split("#")[0].strip()
                if not line:
                    continue
                k, _, v = line.partition(":")
                k, v = k.strip().lower(), v.strip()
                if k == "user-agent":
                    if cur and groups.get(cur[-1], {}).get("_rules"):
                        cur = []
                    cur.append(v.lower())
                    groups.setdefault(v.lower(), {"_rules": []})
                elif k in ("allow", "disallow") and cur:
                    for ua in cur:
                        groups[ua]["_rules"].append((k, v))
            self.robots_groups = groups
            star = groups.get("*", {"_rules": []})["_rules"]
            blocked_all = ("disallow", "/") in star and ("allow", "/") not in star
            if blocked_all:
                a.add("C01", "robots.txt presente e valido", "fail", "User-agent: * Disallow: / — il sito è BLOCCATO ai motori di ricerca", "P0")
            else:
                dis = [v for k, v in star if k == "disallow" and v]
                a.add("C01", "robots.txt presente e valido", "ok",
                      f"{len(groups)} gruppi; sitemap dichiarate: {len(sitemaps)}; Disallow per *: {', '.join(dis[:8]) or 'nessuno'}")
        # sitemap
        urls, notes = [], []
        sm_url = sitemaps[0] if sitemaps else self.url("/sitemap.xml")
        todo, seen = [sm_url], set()
        while todo and len(seen) < 6:
            u = todo.pop(0)
            if u in seen:
                continue
            seen.add(u)
            r = self.http.fetch(u, maxbytes=6_000_000)
            body = Http.text(r)
            if not (r["ok"] and r["status"] == 200 and "<" in body):
                notes.append(f"{u}: status {r['status']}")
                continue
            if "<sitemapindex" in body:
                todo += re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", body)[:5]
            else:
                for blk in re.findall(r"<url>(.*?)</url>", body, re.S):
                    loc = re.search(r"<loc>\s*([^<\s]+)\s*</loc>", blk)
                    lm = re.search(r"<lastmod>\s*([^<\s]+)\s*</lastmod>", blk)
                    if loc:
                        urls.append((loc.group(1), lm.group(1) if lm else None))
        self.sitemap_urls = urls
        if not urls:
            a.add("C02", "sitemap.xml presente e valida", "fail", "; ".join(notes) or "nessun URL trovato")
        else:
            issues = []
            hosts = {host_of(u) for u, _ in urls}
            if any(urllib.parse.urlsplit(u).scheme != "https" for u, _ in urls):
                issues.append("URL non https")
            if any(not same_site(h, self.domain) for h in hosts):
                issues.append("URL di altri domini")
            lms = sorted(lm[:10] for _, lm in urls if lm)
            if lms:
                if len(set(lms)) == 1 and len(urls) > 3:
                    issues.append(f"tutte le lastmod identiche ({lms[0]})")
                try:
                    newest = dt.date.fromisoformat(lms[-1])
                    if (dt.date.today() - newest).days > 90:
                        issues.append(f"lastmod più recente vecchia di {(dt.date.today() - newest).days} giorni")
                except Exception:
                    pass
            else:
                issues.append("nessuna lastmod")
            bad_url = [u for u, _ in urls if re.search(r"[A-Z]|_|\?", urllib.parse.urlsplit(u).path + urllib.parse.urlsplit(u).query)]
            a.add("C02", "sitemap.xml presente e valida", "warn" if issues else "ok",
                  f"{len(urls)} URL; lastmod {lms[0] if lms else '—'} … {lms[-1] if lms else '—'}" + ("; " + "; ".join(issues) if issues else ""))
            a.add("P05", "URL: minuscole, trattini, senza underscore né parametri", "warn" if bad_url else "ok",
                  f"{len(bad_url)} URL non conformi nella sitemap: {', '.join(bad_url[:4])}" if bad_url else "conformi")
        # llms.txt
        ll = self.page(self.url("/llms.txt"))
        lt = ll["html"] if ll["res"]["ok"] and ll["res"]["status"] == 200 else ""
        if not lt or lt.lstrip().lower().startswith("<!doctype") or "<html" in lt[:300].lower():
            a.add("D01", "llms.txt presente", "fail", f"status {ll['res']['status']}")
            a.add("D02", "llms.txt conforme (H1 + link Markdown assoluti)", "na", "llms.txt assente")
        else:
            a.add("D01", "llms.txt presente", "ok", f"{len(lt)} byte")
            links = re.findall(r"\[[^\]]+\]\(([^)]+)\)", lt)
            rel = [x for x in links if not x.startswith("http")]
            probs = []
            if not lt.lstrip().startswith("# "):
                probs.append("manca H1 iniziale")
            if rel:
                probs.append(f"{len(rel)} link relativi")
            if not links:
                probs.append("nessun link Markdown")
            a.add("D02", "llms.txt conforme (H1 + link Markdown assoluti)", "warn" if probs else "ok",
                  "; ".join(probs) or f"H1 presente, {len(links)} link assoluti")
        # crawler AI
        groups = getattr(self, "robots_groups", {})
        status = {}
        for bot in AI_BOTS:
            rules = groups.get(bot.lower(), {}).get("_rules")
            if rules is None:
                rules = groups.get("*", {"_rules": []})["_rules"]
                status[bot] = "bloccato (da *)" if ("disallow", "/") in rules else "consentito"
            else:
                status[bot] = "bloccato" if ("disallow", "/") in rules and ("allow", "/") not in rules else "consentito"
        blocked_key = [b for b in KEY_BOTS if status[b].startswith("bloccato")]
        blk = [b for b, s_ in status.items() if s_.startswith("bloccato")]
        alw = [b for b, s_ in status.items() if not s_.startswith("bloccato")]
        a.add("D03", "robots.txt non blocca i crawler AI principali", "warn" if blocked_key else "ok",
              f"BLOCCATI: {', '.join(blk) or 'nessuno'}{' (verificare che sia una scelta voluta)' if blk else ''} | consentiti: {', '.join(alw)}")
        a.add("D04", "Contenuti answer-first e citabili (fonte, data, autore)", "manual", "richiede revisione editoriale")
        self.run_agent(lt)

    # ---------------------------------------------------------------- D (agent readiness): Markdown, istruzioni, pagine di fiducia
    def run_agent(self, llms_text):
        """Controlli di prontezza per gli agenti AI (negoziazione Markdown, 404, when-to-use, pagine di fiducia).
        Solo richieste in lettura. D05-D07/D11 si applicano se il sito serve Markdown (cfg agent.markdown)."""
        a, cfg = self.a, self.cfg["agent"]
        MD = {"Accept": "text/markdown"}
        BROWSER = {"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"}

        def is_md(r):
            return r["ok"] and r["status"] == 200 and r["headers"].get("content-type", "").lower().startswith("text/markdown") \
                and bool((r["body"] or b"").strip())

        def vary_accept(r):
            return "accept" in [x.strip() for x in r["headers"].get("vary", "").lower().replace("accept-encoding", "").split(",")]

        home_md = self.http.fetch(self.url("/"), headers=MD)
        home_html = self.http.fetch(self.url("/"), headers={"Accept": "text/html"})
        flag = cfg.get("markdown")
        supported = is_md(home_md) if flag is None else bool(flag)
        na_msg = "il sito non serve Markdown (opzionale; impostare [agent].markdown = true per pretenderlo)"

        # D06 negoziazione sulla home
        if not supported and flag is None:
            a.add("D06", "Markdown content negotiation (Accept: text/markdown sulla home)", "na", na_msg)
        else:
            probs = []
            if not is_md(home_md):
                probs.append(f"Accept: text/markdown → {home_md['status']} {home_md['headers'].get('content-type', '?')}")
            elif not vary_accept(home_md):
                probs.append(f"manca Vary: Accept (Vary: {home_md['headers'].get('vary', 'assente')})")
            if "html" not in home_html["headers"].get("content-type", "").lower():
                probs.append("con Accept: text/html la home non risponde HTML")
            a.add("D06", "Markdown content negotiation (Accept: text/markdown sulla home)", "fail" if probs else "ok",
                  "; ".join(probs) or f"text/markdown, Vary: Accept, {len(home_md['body'])} byte; HTML invariato per Accept: text/html")

        # D05 404 con corpo Markdown
        rnd = f"/zz-go-live-agent-{random.Random().randint(10000, 99999)}"
        if not supported:
            a.add("D05", "404 con corpo Markdown per gli agenti", "na", na_msg)
        else:
            r = self.http.fetch(self.url(rnd), headers=MD)
            body = Http.text(r)
            ctype = r["headers"].get("content-type", "").lower()
            has_link = bool(re.search(r"(llms\.txt|sitemap|docs|\]\()", body, re.I))
            probs = []
            if r["status"] != 404:
                probs.append(f"status {r['status']} invece di 404")
            if not ctype.startswith("text/markdown"):
                probs.append(f"Content-Type {ctype or 'assente'}")
            if len(body.strip()) < 20:
                probs.append("corpo < 20 caratteri")
            if not has_link:
                probs.append("nessun link a docs/sitemap/llms.txt")
            a.add("D05", "404 con corpo Markdown per gli agenti", "warn" if (probs and r["status"] == 404) else ("fail" if probs else "ok"),
                  "; ".join(probs) or f"404 text/markdown, {len(body.strip())} caratteri con link")

        # D07 stessa negoziazione su un campione di pagine
        if not supported:
            a.add("D07", "Markdown su un campione di pagine", "na", na_msg)
        else:
            urls = [u for u, _ in getattr(self, "sitemap_urls", []) if self.norm(u) != self.norm(self.base + "/")][:3]
            bad = []
            for u in urls:
                r = self.http.fetch(u, headers=MD)
                if not is_md(r) or not vary_accept(r):
                    bad.append(f"{urllib.parse.urlsplit(u).path} ({r['status']} {r['headers'].get('content-type', '?')[:30]})")
            a.add("D07", "Markdown su un campione di pagine", "manual" if not urls else ("warn" if bad else "ok"),
                  "sitemap senza URL" if not urls else (f"non in Markdown: {', '.join(bad)}" if bad else f"{len(urls)} pagine ok"))

        # D11 il browser non riceve mai Markdown
        if not supported:
            a.add("D11", "Un browser (Accept: text/html,*/*) non riceve mai Markdown", "na", na_msg)
        else:
            r = self.http.fetch(self.url("/"), headers=BROWSER)
            r2 = self.http.fetch(self.url("/"), headers={"Accept": "*/*"})
            leak = [n for n, x in (("browser", r), ("*/*", r2)) if x["headers"].get("content-type", "").lower().startswith("text/markdown")]
            a.add("D11", "Un browser (Accept: text/html,*/*) non riceve mai Markdown", "fail" if leak else "ok",
                  f"Markdown servito con Accept {', '.join(leak)}: rischio di cache che serve Markdown ai browser" if leak else "HTML con Accept da browser e con */*")

        # D08 'when to use' per agenti
        pat = re.compile(r"^#{1,3}\s.*(when to use|quando usare|quando (?:consigliare|citare|rivolgersi)|use cases|casi d.uso)", re.I | re.M)
        src, text = None, ""
        if llms_text and pat.search(llms_text):
            src, text = "llms.txt", llms_text
        else:
            for pth in ("/AGENTS.md", "/agents.md", "/.well-known/agents.md"):
                r = self.http.fetch(self.url(pth))
                t = Http.text(r) if r["ok"] and r["status"] == 200 else ""
                if t and not t.lstrip().lower().startswith("<!doctype") and pat.search(t):
                    src, text = pth, t
                    break
        if src:
            m = pat.search(text)
            section = text[m.end():].split("\n## ")[0]
            substantive = len(section.strip()) >= 150
            a.add("D08", "Istruzioni per agenti: sezione 'when to use' (llms.txt o AGENTS.md)", "ok" if substantive else "warn",
                  f"in {src}, {len(section.strip())} caratteri" + ("" if substantive else " (troppo breve: servono casi d'uso concreti)"))
        else:
            a.add("D08", "Istruzioni per agenti: sezione 'when to use' (llms.txt o AGENTS.md)", "warn",
                  "nessuna sezione 'when to use / quando usare' in llms.txt, /AGENTS.md né /.well-known/agents.md")

        # D10 pagine di fiducia con contenuto reale
        lg, minc = self.cfg["legal"], cfg.get("trust_min_chars", 500)
        groups = (("about", lg["about_paths"]), ("contact", cfg["contact_paths"]), ("privacy", lg["privacy_paths"]))
        found, missing = [], []
        for name, paths in groups:
            pth, pg = self.first_ok(paths)
            n = len(html_to_text(pg["html"])) if pg else 0
            (found if pth and n >= minc else missing).append(f"{name}: {pth or 'assente'}" + (f" ({n} car.)" if pth else ""))
        a.add("D10", f"Pagine di fiducia (about, contact, privacy) con ≥ {minc} caratteri", "warn" if missing else "ok",
              ("mancanti o troppo brevi: " + "; ".join(missing) + (" | ok: " + "; ".join(found) if found else "")) if missing else "; ".join(found))

        # D12 brand discoverability: serve una ricerca web
        a.add("D12", "Brand discoverability (il dominio compare nei primi 10 per marchio + prodotto)", "manual",
              f"cercare \"{self.cfg['name']}\" e \"{self.cfg['name']} + prodotto principale\" su un motore di ricerca; richiede Search Console per la copertura")

    # ---------------------------------------------------------------- campione di pagine
    def choose_sample(self):
        cr = self.cfg["crawl"]
        want = [self.base + "/"]
        lg = self.cfg["legal"]
        for key in ("privacy_paths", "terms_paths", "cookie_paths"):
            pth, _ = self.first_ok(lg[key])
            if pth:
                want.append(self.url(pth))
        want += [self.url(p) for p in cr["sample_paths"]]
        groups = {}
        for u, _ in getattr(self, "sitemap_urls", []):
            if not same_site(host_of(u), self.domain):
                continue
            seg = urllib.parse.urlsplit(u).path.strip("/").split("/")[0] or "/"
            groups.setdefault(seg, []).append(u)
        pool = []
        i = 0
        while any(groups.values()):
            for seg in sorted(groups):
                if groups[seg]:
                    pool.append(groups[seg].pop(0))
            i += 1
            if i > 50:
                break
        sample = list(dict.fromkeys(self.norm(u) for u in want + pool))[: cr["max_pages"]]
        self.sample = sample
        for u in sample:
            self.page(u)
        self.a.facts["sample"] = sample

    # ---------------------------------------------------------------- pagine campione: P, Q, I, C, L, R, N
    def run_pages(self):
        a, cfg = self.a, self.cfg
        T = {"title_min": 30, "title_max": 65, "desc_min": 70, "desc_max": 165, "thin_words": 300}
        okp = [pg for pg in self.pages.values() if pg["p"] and pg["res"]["status"] == 200 and pg["url"] in self.sample]
        self.okpages = okp
        a.facts["pages_ok"] = len(okp)
        bad_title, bad_desc, no_h1, multi_h1, no_canon, bad_canon, thin, noidx, no_og = [], [], [], [], [], [], [], [], []
        no_tw, jumps, no_lang, no_main, forms_nolabel, hr_issues = [], [], [], [], [], []
        imgs_total = imgs_noalt = imgs_nolazy = imgs_legacy = imgs_srcset = 0
        formats = {}
        jsonld_types = {}
        home_types = set()
        gsc = ga4 = None
        for pg in okp:
            p, u = pg["p"], pg["url"]
            path = urllib.parse.urlsplit(u).path or "/"
            tl = len(p.title)
            if not (T["title_min"] <= tl <= T["title_max"]):
                bad_title.append(f"{path} ({tl})")
            d = p.meta("description")
            if d is None or not (T["desc_min"] <= len(d) <= T["desc_max"]):
                bad_desc.append(f"{path} ({len(d) if d is not None else 'assente'})")
            h1 = [h for h in p.headings if h[0] == 1]
            if not h1:
                no_h1.append(path)
            if len(h1) > 1:
                multi_h1.append(f"{path} ({len(h1)})")
            lv = [h[0] for h in p.headings]
            if any(b - a_ > 1 for a_, b in zip(lv, lv[1:])):
                jumps.append(path)
            can = p.link_rel("canonical")
            if not can:
                no_canon.append(path)
            else:
                cu = urllib.parse.urljoin(u, can[0].get("href", ""))
                if cu.rstrip("/") != u.rstrip("/").split("#")[0].split("?")[0]:
                    bad_canon.append(f"{path} → {cu}")
            robots_meta = (p.meta("robots") or "").lower() + " " + pg["res"]["headers"].get("x-robots-tag", "").lower()
            if "noindex" in robots_meta and not any(path.startswith(x) for x in cfg["noindex_ok"]):
                noidx.append(path)
            if not (p.meta("og:title", "property") and p.meta("og:description", "property") and p.meta("og:image", "property")):
                no_og.append(path)
            if not p.meta("twitter:card") or not p.meta("twitter:image"):
                no_tw.append(path)
            if not p.lang:
                no_lang.append(path)
            if "main" not in p.landmarks and "role:main" not in p.landmarks:
                no_main.append(path)
            legal_like = any(k in path for k in ("privacy", "termini", "cookie", "terms", "accessib"))
            if p.body_words < T["thin_words"] and not legal_like:
                thin.append(f"{path} ({p.body_words} parole)")
            for im in p.imgs:
                imgs_total += 1
                if "alt" not in im:
                    imgs_noalt += 1
                if im.get("loading") != "lazy" and not im.get("fetchpriority") and not im.get("priority"):
                    imgs_nolazy += 1
                src = im.get("src", "")
                ext = re.search(r"\.(avif|webp|png|jpe?g|gif|svg)(\?|$)", src.lower())
                fmt = ext.group(1) if ext else ("next/image" if "_next/image" in src else "altro")
                formats[fmt] = formats.get(fmt, 0) + 1
                if fmt in ("png", "jpg", "jpeg", "gif"):
                    imgs_legacy += 1
                if im.get("srcset"):
                    imgs_srcset += 1
            for f in p.forms:
                miss = 0
                for tag, at in f["inputs"]:
                    if at.get("type") in ("hidden", "submit", "button", "image", "reset"):
                        continue
                    if not (at.get("id") in p.labels_for or at.get("aria-label") or at.get("aria-labelledby") or at.get("title")):
                        miss += 1
                if miss:
                    forms_nolabel.append(f"{path} ({miss} campi)")
            for raw in p.jsonld:
                try:
                    data = json.loads(raw)
                except Exception:
                    continue
                nodes = data if isinstance(data, list) else data.get("@graph", [data]) if isinstance(data, dict) else []
                for n in nodes:
                    if isinstance(n, dict):
                        t = n.get("@type")
                        for tt in (t if isinstance(t, list) else [t]):
                            jsonld_types.setdefault(str(tt), []).append(path)
                            if u.rstrip("/") == self.base.rstrip("/"):
                                home_types.add(str(tt))
            if pg["url"].rstrip("/") == self.base.rstrip("/"):
                g = p.meta("google-site-verification")
                gsc = g
            blob = " ".join(p.inline_scripts) + " ".join(s.get("src", "") for s in p.scripts)
            m = re.search(r"\bG-[A-Z0-9]{6,12}\b", blob)
            if m and not ga4:
                ga4 = m.group(0)
        n = len(okp)
        a.facts["jsonld_types"] = {k: sorted(set(v)) for k, v in jsonld_types.items()}

        def agg(cid, title, bad, okmsg, level="warn", extra=""):
            a.add(cid, title, level if bad else "ok", (f"{len(bad)}/{n} pagine: " + ", ".join(bad[:6]) + (" …" if len(bad) > 6 else "") + extra) if bad else okmsg)
        agg("C03", "Canonical su tutte le pagine campione, autoreferenziato", no_canon + bad_canon, f"{n} pagine ok")
        a.add("C04", "Meta title e description presenti", "ok" if n and not [x for x in bad_title if "(0)" in x] and not [x for x in bad_desc if "assente" in x] else "warn",
              f"title fuori misura: {len(bad_title)}; description fuori misura/assenti: {len(bad_desc)} su {n} pagine")
        agg("C05", "OG tags (title, description, image) su tutte le pagine campione", no_og, f"{n} pagine ok")
        agg("C06", "Twitter/X card (card + image)", no_tw, f"{n} pagine ok")
        tl = jsonld_types
        has_org = any(t in home_types for t in ("Organization", "Corporation", "LocalBusiness", "NewsMediaOrganization"))
        has_site = "WebSite" in home_types
        a.add("C08", "Schema.org Organization/WebSite in homepage", "ok" if has_org and has_site else ("warn" if has_org or has_site else "fail"),
              f"tipi nella homepage: {', '.join(sorted(home_types)) or 'nessuno'}")
        page_specific = [t for t in tl if t in ("Article", "BlogPosting", "NewsArticle", "FAQPage", "HowTo", "Product", "BreadcrumbList", "Service", "Offer", "ItemList", "Review")]
        a.add("C09", "Schema.org specifico per le pagine (Article, FAQ, Breadcrumb, …)", "ok" if page_specific else "warn",
              ", ".join(f"{t} su {len(set(tl[t]))} pag." for t in page_specific) or "nessuno nelle pagine campionate")
        a.add("C10", "GA4 configurato", "ok" if ga4 else "warn", ga4 or "ID G-… non trovato nel HTML (potrebbe essere in GTM)")
        a.add("C11", "Google Search Console: meta tag di verifica", "warn" if gsc else "fail",
              (f"meta presente ({gsc[:8]}…): la verifica completata non è controllabile da fuori" if gsc else "assente (la verifica può essere via DNS/file: controllare in GSC)"))
        a.add("C12", "Search Console: verifica completata, sitemap inviata, copertura", "manual", "serve accesso a GSC")
        a.add("C13", "GA4 collegato a Search Console", "manual", "serve accesso a GA4")
        # P
        tit = "ok" if not bad_title else "warn"
        a.add("P01", f"Title {T['title_min']}-{T['title_max']} caratteri", tit,
              (f"fuori misura: {', '.join(bad_title[:6])}" if bad_title else f"{n} pagine ok"))
        a.add("P02", f"Description {T['desc_min']}-{T['desc_max']} caratteri", "ok" if not bad_desc else "warn",
              (f"fuori misura/assenti: {', '.join(bad_desc[:6])}" if bad_desc else f"{n} pagine ok"))
        a.add("P03", "H1 presente e unico", "fail" if no_h1 else ("warn" if multi_h1 else "ok"),
              "; ".join(x for x in (("senza H1: " + ", ".join(no_h1[:5])) if no_h1 else "", ("più H1: " + ", ".join(multi_h1[:5])) if multi_h1 else "") if x) or f"{n} pagine ok")
        og_dim = []
        for pg in okp[:6]:
            w, h_ = pg["p"].meta("og:image:width", "property"), pg["p"].meta("og:image:height", "property")
            if pg["p"].meta("og:image", "property") and not (w and h_ and int(w) >= 1200 and int(h_) >= 630):
                og_dim.append(urllib.parse.urlsplit(pg["url"]).path or "/")
        a.add("P04", "og:image:width ≥ 1200 e height ≥ 630 dichiarati", "warn" if og_dim else "ok",
              ("dimensioni mancanti/inferiori su: " + ", ".join(og_dim)) if og_dim else "dichiarate")
        agg("P06", "noindex solo su pagine non destinate all'indice", noidx, "nessun noindex inatteso", "fail")
        agg("P07", "Thin content (< 300 parole, escluse pagine legali)", thin, "nessuna pagina sottile nel campione")
        agg("I07", "Gerarchia dei titoli senza salti (h1→h2→h3)", jumps, f"{n} pagine ok")
        # I
        a.add("I01", "Attributo lang su <html>", "fail" if no_lang else "ok", ("assente su " + ", ".join(no_lang[:5])) if no_lang else f"lang presente su {n} pagine")
        skip = any(any(("skip" in (x["attrs"].get("class", "") + x["attrs"].get("href", "")).lower() or "salta" in x["text"].lower() or "skip to" in x["text"].lower())
                       and x["attrs"].get("href", "").startswith("#") for x in pg["p"].anchors) for pg in okp[:5])
        a.add("I02", "Skip link (\"Salta al contenuto\")", "ok" if skip else "warn", "presente" if skip else "non trovato nelle prime pagine")
        a.add("I03", "Tutte le <img> hanno attributo alt", "fail" if imgs_noalt else "ok", f"{imgs_noalt} senza alt su {imgs_total} immagini ({n} pagine)")
        land_ok = all({"main", "nav"} <= pg["p"].landmarks | {x.replace("role:", "") for x in pg["p"].landmarks} for pg in okp[:5])
        a.add("I04", "Landmark ARIA/HTML (main, nav, footer)", "ok" if land_ok else "warn",
              f"main assente su: {', '.join(no_main[:5])}" if no_main else "main/nav presenti")
        pth, _ = self.first_ok(self.cfg["legal"]["accessibility_paths"])
        a.add("I05", "Dichiarazione di accessibilità presente", "ok" if pth else "fail",
              pth or "nessuna tra " + ", ".join(self.cfg["legal"]["accessibility_paths"]) + " risponde 200")
        vp = self.home["p"].meta("viewport") or ""
        vbad = re.search(r"user-scalable\s*=\s*(no|0)|maximum-scale\s*=\s*1(\.0)?\b", vp)
        a.add("I09", "Viewport senza blocco dello zoom", "fail" if vbad else ("ok" if vp else "warn"), vp or "meta viewport assente")
        agg("I08", "Campi dei form con etichetta accessibile", forms_nolabel, "tutti etichettati (o nessun form)")
        noname = 0
        for pg in okp[:8]:
            for x in pg["p"].anchors:
                if not x["text"] and not x["attrs"].get("aria-label") and not x["attrs"].get("title"):
                    noname += 1
        a.add("I10", "Link con nome accessibile", "warn" if noname else "ok", f"{noname} link senza testo/aria-label (prime 8 pagine; i link con sola immagine con alt non sono distinguibili qui)" if noname else "tutti con nome")
        # Q
        a.add("Q01", "Alt text su tutte le immagini", "fail" if imgs_noalt else ("na" if not imgs_total else "ok"), f"{imgs_noalt}/{imgs_total} senza alt")
        a.add("Q02", "Formati moderni (WebP/AVIF/SVG o next/image)", "na" if not imgs_total else ("warn" if imgs_legacy else "ok"),
              f"formati: {formats}; legacy (png/jpg/gif): {imgs_legacy}")
        a.add("Q03", "Lazy loading sulle immagini sotto la piega", "na" if not imgs_total else ("warn" if imgs_nolazy > max(1, imgs_total // 2) else "ok"),
              f"{imgs_nolazy}/{imgs_total} senza loading=lazy")
        a.add("Q04", "Immagini responsive (srcset)", "na" if not imgs_total else ("warn" if imgs_srcset == 0 else "ok"), f"{imgs_srcset}/{imgs_total} con srcset")
        a.facts["images"] = {"total": imgs_total, "formats": formats}
        # L: form
        forms = [(pg["url"], f) for pg in okp for f in pg["p"].forms]
        scripts_all = " ".join(" ".join(s.get("src", "") for s in pg["p"].scripts) + " ".join(pg["p"].inline_scripts)[:20000] for pg in okp)
        frames = " ".join(i.get("src", "") for pg in okp for i in pg["p"].iframes)
        csp = self.a.facts.get("csp", "")
        captcha = re.findall(r"recaptcha|hcaptcha|turnstile|friendlycaptcha", scripts_all + frames + csp, re.I)
        honey = [(u, i[1].get("name")) for u, f in forms for i in f["inputs"] if i[1].get("type") == "hidden" and re.search(r"honey|hp|bot|website|url|trap", i[1].get("name", ""), re.I)]
        a.add("L01", "Form rilevati nelle pagine campione", "na" if not forms else "ok", f"{len(forms)} form" if forms else "nessun form nelle pagine campionate (potrebbero essere caricati lato client)")
        a.add("L02", "Honeypot o captcha", "na" if not forms and not captcha else ("ok" if captcha or honey else "warn"),
              f"captcha: {sorted(set(c.lower() for c in captcha)) or '—'}; honeypot: {len(honey)}")
        a.add("L03", "Validazione server-side, rate limiting, test input malformati", "manual", "non verificabile senza inviare dati ai form")
        # N
        multi = cfg["multilingual"] or any(pg["p"].link_rel("alternate") and any(l.get("hreflang") for l in pg["p"].links) for pg in okp)
        if not multi:
            a.add("N01", "Hreflang (solo siti multilingua)", "na", "sito monolingua, nessun hreflang trovato")
        else:
            miss, noxd, rel = [], [], []
            for pg in okp[:8]:
                hl = [l for l in pg["p"].links if l.get("hreflang")]
                path = urllib.parse.urlsplit(pg["url"]).path or "/"
                if not hl:
                    miss.append(path)
                    continue
                if not any(l.get("hreflang") == "x-default" for l in hl):
                    noxd.append(path)
                rel += [path for l in hl if not l.get("href", "").startswith("http")]
            a.add("N01", "Hreflang: presente, x-default, URL assoluti", "warn" if (miss or noxd or rel) else "ok",
                  f"senza hreflang: {miss[:4]}; senza x-default: {noxd[:4]}; relativi: {sorted(set(rel))[:4]}")
        self.imgs_total = imgs_total

    # ---------------------------------------------------------------- M: link
    def run_M(self):
        a, cr = self.a, self.cfg["crawl"]
        internal, external = {}, {}
        for pg in self.okpages:
            for x in pg["p"].anchors:
                href = x["attrs"].get("href", "").strip()
                if not href or href.startswith(("#", "mailto:", "tel:", "javascript:", "sms:")):
                    continue
                full = urllib.parse.urljoin(pg["url"], href).split("#")[0]
                host = host_of(full)
                (internal if same_site(host, self.domain) else external).setdefault(full, pg["url"])
        internal = {u: s for u, s in internal.items() if "/cdn-cgi/" not in u and not re.search(r"\.(png|jpe?g|webp|avif|svg|ico|css|js|pdf|zip|woff2?)(\?|$)", u.lower())}
        bad, redir, checked, unverified = [], [], 0, []
        for u, src in list(internal.items())[: cr["max_link_checks"]]:
            if u in self.pages:
                r = self.pages[u]["res"]
            else:
                r = self.http.fetch(u, follow=False, method="HEAD")
                if r["ok"] and r["status"] in (403, 405, 501):
                    r = self.http.fetch(u, follow=False)
            checked += 1
            if not r["ok"]:  # nessuna risposta HTTP: errore di rete dal server di audit, NON un link rotto
                unverified.append(f"{u} → {short(r['error'], 60)}")
            elif r["status"] >= 400:
                bad.append(f"{u} → {r['status']} (da {urllib.parse.urlsplit(src).path})")
            elif 300 <= r["status"] < 400:
                redir.append(f"{u} → {r['status']}")
        a.add("M01", "Nessun link interno rotto (404/5xx) nelle pagine campione", "fail" if bad else ("warn" if unverified else "ok"),
              (f"{len(bad)} rotti su {checked} controllati: " + "; ".join(bad[:5])) if bad else
              (f"{checked} link interni controllati, nessuno rotto" +
               (f"; {len(unverified)} NON verificati per errore di rete dal server di audit dopo 3 tentativi: {'; '.join(unverified[:3])}" if unverified else "") +
               (f"; {len(redir)} con redirect (aggiornare il link)" if redir else "")))
        if redir and not bad:
            a.get("M01")["status"] = "ok"
        eb, ec = [], 0
        for u, src in list(external.items())[: cr["max_external_checks"]]:
            r = self.http.fetch(u, follow=True, method="HEAD", polite=False)
            time.sleep(0.4)
            if not r["ok"]:  # errore di rete: riprova una volta dopo una pausa prima di concludere qualcosa
                time.sleep(3)
                r = self.http.fetch(u, follow=True, method="GET", polite=False, maxbytes=200_000)
            elif r["status"] >= 400:
                r = self.http.fetch(u, follow=True, method="GET", polite=False, maxbytes=200_000)  # HEAD spesso non supportato
            if r["ok"] and r["status"] in (403, 405, 429, 999, 501):
                continue  # blocca i bot: non è un link rotto
            ec += 1
            if not r["ok"]:
                err = r["error"] or ""
                if re.search(r"nodename|Name or service|getaddrinfo|Temporary failure", err):
                    rr, vv = doh_values(host_of(u), "A")
                    eb.append(f"{u} → dominio non risolvibile (DoH: {'nessun record A' if rr['ok'] and not vv else 'verifica fallita'})")
                else:
                    eb.append(f"{u} → {short(err, 50)} (errore di rete dal server di audit dopo 2 tentativi: ricontrollare, non conferma un link rotto)")
            elif r["status"] >= 400:
                eb.append(f"{u} → {r['status']}")
        a.add("M02", "Nessun link esterno rotto nelle pagine campione", "warn" if eb else ("na" if not external else "ok"),
              ("; ".join(eb[:5])) if eb else f"{ec} link esterni controllati su {len(external)} trovati")
        ids_bad = []
        for pg in self.okpages[:10]:
            anchors = {x["attrs"].get("href") for x in pg["p"].anchors if x["attrs"].get("href", "").startswith("#") and len(x["attrs"].get("href", "")) > 1}
            if anchors and pg["html"]:
                missing = [h for h in anchors if f'id="{h[1:]}"' not in pg["html"] and f"id='{h[1:]}'" not in pg["html"] and f'name="{h[1:]}"' not in pg["html"]]
                if missing:
                    ids_bad.append(f"{urllib.parse.urlsplit(pg['url']).path or '/'}: {', '.join(missing[:3])}")
        a.add("M03", "Anchor interni (#id) funzionanti", "warn" if ids_bad else "ok", "; ".join(ids_bad[:4]) or "nessun anchor orfano nelle prime 10 pagine")
        # stato URL della sitemap (campione)
        su = [u for u, _ in getattr(self, "sitemap_urls", [])]
        random.Random(7).shuffle(su)
        nonok = []
        for u in su[:12]:
            if u in self.pages:
                r = self.pages[u]["res"]
            else:
                r = self.http.fetch(u, follow=False, method="HEAD")
            if not r["ok"] or r["status"] != 200:
                nonok.append(f"{u} → {r['status'] or r['error']}")
        a.add("M04", "URL della sitemap rispondono 200 (campione di 12)", "warn" if nonok else ("na" if not su else "ok"),
              "; ".join(nonok[:4]) or f"{min(12, len(su))} controllati")

    # ---------------------------------------------------------------- asset: JS/CSS (G, I, J, E, B)
    def run_assets(self):
        a = self.a
        home = self.home["p"]
        scripts = [urllib.parse.urljoin(self.base + "/", s["src"]) for s in home.scripts if s.get("src")]
        fp = [s for s in scripts if same_site(host_of(s), self.domain)]
        css = [urllib.parse.urljoin(self.base + "/", l["href"]) for l in home.link_rel("stylesheet") if l.get("href")]
        css_fp = [c for c in css if same_site(host_of(c), self.domain)]
        total_js, cache_ok, cache_bad, secrets = 0, 0, [], []
        pat = {"AWS key": r"AKIA[0-9A-Z]{16}", "chiave privata": r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
               "Stripe live": r"sk_live_[0-9a-zA-Z]{20,}", "Slack": r"xox[baprs]-[0-9A-Za-z-]{10,}", "GitHub": r"gh[pousr]_[A-Za-z0-9]{36}"}
        for s in fp[:25]:
            r = self.asset(s)
            if not r["ok"] or r["status"] != 200:
                continue
            total_js += r["raw_len"]
            txt = r["body"].decode("utf-8", "ignore")
            self.js_texts[s] = txt
            for k, rx in pat.items():
                if re.search(rx, txt):
                    secrets.append(f"{k} in {s.rsplit('/', 1)[-1]}")
            if "/cdn-cgi/" in s:
                continue  # script di Cloudflare, non gestito dal sito
            cc = r["headers"].get("cache-control", "").lower()
            m = re.search(r"max-age=(\d+)", cc)
            if "immutable" in cc or (m and int(m.group(1)) >= 31536000):
                cache_ok += 1
            else:
                cache_bad.append(f"{s.rsplit('/', 1)[-1]}: {cc or 'nessuna'}")
        kb = total_js / 1024
        a.add("G04", "JS first-party trasferito < 200 kB", "na" if not fp else ("ok" if kb < 200 else ("warn" if kb < 400 else "fail")),
              f"{len(fp)} script first-party nell'HTML della home, {kb:.0f} kB trasferiti (compressi); esclusi i chunk caricati dopo")
        a.add("G05", "Cache-Control lungo sugli asset statici", "na" if not fp else ("warn" if cache_bad else "ok"),
              f"{cache_ok} con max-age ≥ 1 anno/immutable; fuori regola: {'; '.join(cache_bad[:3]) or '—'}")
        a.add("B12", "Nessun segreto noto nei bundle JS first-party", "fail" if secrets else "ok",
              "; ".join(secrets) if secrets else f"nessun pattern noto in {len(self.js_texts)} script (non è un'analisi completa)")
        focus = False
        font_display = False
        for c in css_fp[:5]:
            r = self.asset(c)
            if r["ok"] and r["status"] == 200:
                t = r["body"].decode("utf-8", "ignore")
                self.css_texts[c] = t
                focus = focus or ":focus-visible" in t or ":focus" in t
                font_display = font_display or "font-display" in t
        a.add("I06", ":focus / :focus-visible definiti nel CSS", "na" if not css_fp else ("ok" if focus else "warn"),
              f"{len(self.css_texts)} fogli di stile first-party letti" + ("" if focus else "; nessuna regola :focus trovata"))
        pre_font = [l for l in home.links if "preload" in l.get("rel", "") and l.get("as") == "font"]
        a.add("G06", "Font ottimizzati (preload e/o font-display)", "ok" if (pre_font or font_display) else "warn",
              f"preload font: {len(pre_font)}; font-display nel CSS: {'sì' if font_display else 'no'}")
        r = self.home["res"]
        enc = r["headers"].get("content-encoding", "")
        a.add("G02", "Compressione del testo (gzip/br)", "ok" if enc else "warn", f"content-encoding: {enc or 'nessuna'}")
        t = sorted(self.http.fetch(self.base + "/")["elapsed"] for _ in range(3))
        a.add("G01", "TTFB/risposta HTML < 0.8 s (mediana di 3, dal punto di vista di questo server)", "ok" if t[1] < 0.8 else ("warn" if t[1] < 1.5 else "fail"),
              f"mediana {t[1]:.2f}s (min {t[0]:.2f}s, max {t[2]:.2f}s); HTML {len(self.home['html']) / 1024:.0f} kB")
        for cid, title in (("G07", "Lighthouse Performance ≥ 90"), ("G08", "LCP < 2.5 s"), ("G09", "INP < 200 ms"), ("G10", "CLS < 0.1")):
            a.add(cid, title, "manual", "richiede browser reale (modulo browser/Lighthouse)")
        # J: monitoring
        blob = " ".join(self.js_texts.values())[:3_000_000] + " ".join(" ".join(pg["p"].inline_scripts) for pg in self.okpages if pg["p"])[:2_000_000] + self.a.facts.get("csp", "")
        mon = re.findall(r"sentry|bugsnag|datadog|rollbar|logrocket|highlight\.io|newrelic|appsignal|glitchtip|honeybadger", blob, re.I)
        a.add("J01", "Error monitoring (Sentry o equivalente)", "ok" if mon else "warn", (f"rilevato: {sorted(set(m.lower() for m in mon))}" if mon else "non rilevato lato client (può essere solo server-side)"))
        a.add("J02", "Uptime monitoring esterno HTTP + DNS con alert", "manual", "senza una fonte indipendente non si distingue un outage da un problema di rete locale")
        a.add("J03", "Log di produzione e dashboard KPI", "manual", "non verificabile dall'esterno")

    # ---------------------------------------------------------------- E, F, H, R, S: legale, azienda, coerenza
    def run_legal_company(self):
        a, lg = self.a, self.cfg["legal"]
        found = {}
        for key, cid, title in (("privacy_paths", "E01", "Privacy Policy"), ("terms_paths", "E02", "Termini e Condizioni"), ("cookie_paths", "E03", "Cookie Policy")):
            pth, pg = self.first_ok(lg[key])
            found[key] = (pth, pg)
            a.add(cid, f"{title} raggiungibile", "ok" if pth else "fail", pth or "nessun percorso tra " + ", ".join(lg[key]) + " risponde 200")
            if pg:
                self.legal_text[key] = html_to_text(pg["html"])
        priv = self.legal_text.get("privacy_paths", "")
        cook = self.legal_text.get("cookie_paths", "")
        terms = self.legal_text.get("terms_paths", "")
        # E04 banner
        home_html = self.home["html"]
        all_js = " ".join(self.js_texts.values())
        marker = re.search(r"iubenda|cookiebot|onetrust|cookie[-_ ]?banner|cookie[-_ ]?consent|CookieBanner|cookieyes|complianz|klaro|consent-banner", home_html + all_js, re.I)
        a.add("E04", "Cookie banner presente", "ok" if marker else "manual",
              f"riferimento trovato: '{marker.group(0)}'" if marker else "nessun riferimento nel HTML/JS: il banner può essere caricato lato client; verificare nel browser (modulo browser)")
        # E05 consent mode
        blob = home_html + all_js
        has_ga = bool(re.search(r"googletagmanager|gtag\(|G-[A-Z0-9]{6,}", blob))
        cm = re.search(r"consent['\"]?\s*,\s*['\"]default['\"]", blob)
        if not has_ga:
            a.add("E05", "Consent Mode v2 (analytics negato di default)", "na", "nessun Google Analytics/Tag Manager rilevato")
        else:
            seg = blob[cm.start(): cm.start() + 700] if cm else ""
            need = ["analytics_storage", "ad_storage", "ad_user_data", "ad_personalization"]
            miss = [n for n in need if n not in seg]
            denied = len(re.findall(r"denied", seg))
            if cm and not miss and denied >= 4:
                a.add("E05", "Consent Mode v2 (analytics negato di default)", "ok", "default 'denied' per analytics_storage, ad_storage, ad_user_data, ad_personalization")
            elif cm:
                a.add("E05", "Consent Mode v2 (analytics negato di default)", "warn", f"default impostato ma incompleto: mancano {miss or 'valori denied'}")
            else:
                a.add("E05", "Consent Mode v2 (analytics negato di default)", "fail", "Google tag presente ma nessun gtag('consent','default',…) trovato")
        ck = [c.split("=")[0].strip() for c in self.home["res"]["set_cookie"]]
        an = [c for c in ck if ANALYTICS_COOKIES.match(c)]
        self.a.facts["cookies_first_response"] = ck
        a.add("E06", "Nessun cookie di analytics impostato prima del consenso (prima risposta)", "fail" if an else "ok",
              f"cookie analytics impostati dal server: {an}" if an else f"cookie sulla prima risposta: {ck or 'nessuno'}; i cookie impostati da JS dopo il caricamento richiedono il browser")
        rv = bool(re.search(r"revoc|modific\w+ (le )?(tue )?(preferenze|consens)|gestisci|impostazioni cookie|preferenze", cook, re.I))
        a.add("E07", "Revoca/modifica del consenso descritta nella cookie policy", "na" if not cook else ("ok" if rv else "warn"), "trovata" if rv else "non trovata")
        mail_obf = "email-protection" in " ".join(pg["html"] for pg in (found["privacy_paths"][1],) if pg)
        priv_mail = re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", priv)
        mt = any(x["attrs"].get("href", "").startswith("mailto:") for pg in [found["privacy_paths"][1]] if pg for x in pg["p"].anchors)
        a.add("E08", "Indirizzo email per richieste privacy presente", "ok" if (priv_mail or mt) else ("warn" if mail_obf else "fail" if priv else "na"),
              (priv_mail.group(0) if priv_mail else "mailto presente" if mt else "indirizzo offuscato da Cloudflare: non leggibile da script" if mail_obf else "nessun indirizzo"))
        checks = {
            "titolare del trattamento": r"titolare del trattamento|data controller",
            "base giuridica": r"base giuridica|art\.?\s*6|legittimo interesse",
            "conservazione/retention": r"conserv|retention|per quanto tempo|per il tempo",
            "diritti dell'interessato": r"diritt\w+ (di|dell)|artt?\.?\s*1[5-9]|accesso, rettifica|cancellazione",
            "reclamo al Garante": r"garante",
            "trasferimenti extra-UE": r"extra[- ]?ue|paesi terzi|clausole contrattuali|data privacy framework|scc\b|fuori dall.unione",
            "DPO": r"\bdpo\b|responsabile della protezione dei dati|data protection officer",
        }
        miss = [k for k, rx in checks.items() if not re.search(rx, priv, re.I)] if priv else []
        a.add("E09", "Privacy: elementi tecnici attesi presenti (non è un giudizio legale)", "na" if not priv else ("warn" if miss else "ok"),
              ("non trovati nel testo: " + ", ".join(miss) + " (da confrontare con la realtà e con un legale)") if miss else "tutti presenti nel testo")
        dates = {}
        for k, t in (("privacy", priv), ("cookie", cook), ("termini", terms)):
            m = re.search(r"(?:ultimo aggiornamento|aggiornat[oa]|ultima modifica|last updated)[:\s]*(?:il |a )?([0-9]{1,2}\s+\w+\s+20\d\d|\w+\s+20\d\d|\d{1,2}/\d{1,2}/20\d\d)", t, re.I)
            if m:
                dates[k] = m.group(1)
        a.add("E10", "Date di aggiornamento coerenti tra le pagine legali", "warn" if len(set(dates.values())) > 1 else ("na" if len(dates) < 2 else "ok"),
              "; ".join(f"{k}: {v}" for k, v in dates.items()) or "nessuna data trovata")
        for cid, t in (("E11", "Revisione legale complessiva (base giuridica per ogni trattamento, retention, DPIA)"),):
            a.add(cid, t, "manual", "sempre da far rivedere a un professionista")
        # F: company
        foot = self.home["p"].footer()
        fl = foot + " " + (self.legal_text.get("privacy_paths", "")[:1500])
        piva = re.findall(r"(?:P\.?\s*IVA|partita iva|VAT)[^\d]{0,15}((?:IT)?\s?\d{11})", foot, re.I)
        pv = re.sub(r"\D", "", piva[0]) if piva else None
        company = re.search(r"\b([A-ZÀ-Ý][\w&.' -]{1,40}\s(?:S\.?r\.?l\.?s?|S\.?p\.?A\.?|S\.?n\.?c\.?|S\.?a\.?s\.?|Ltd|GmbH|Inc|LLC))", foot)
        addr = re.search(r"\b(Via|Viale|Piazza|Piazzale|Calle|Corso|Largo|Strada|Vicolo|Campo|Fondamenta|Street|Str\.)\s[\w'’ .,]{2,45}?\d+\s*[,—–-]?\s*(\d{5})?", foot)
        a.add("F01", "Footer: ragione sociale", "ok" if company else "fail", company.group(1) if company else "non riconosciuta (cercare Srl/SpA/… nel footer)")
        a.add("F02", "Footer: P.IVA / VAT", "fail" if not pv else ("ok" if piva_valid(pv) else "warn"),
              (f"{pv} — checksum {'valido' if piva_valid(pv) else 'NON valido'}") if pv else "assente nel footer")
        a.add("F03", "Footer: indirizzo sede", "ok" if addr else "fail", addr.group(0).strip() if addr else "non riconosciuto")
        has_mail = bool(re.search(r"@", foot)) or any(x["attrs"].get("href", "").startswith("mailto:") or "email-protection" in x["attrs"].get("href", "") for x in self.home["p"].anchors)
        a.add("F04", "Footer: email di contatto", "ok" if has_mail else "warn", "presente (anche offuscata)" if has_mail else "assente")
        tel = re.search(r"(\+39[\s\d.-]{6,14}|tel:[+\d]+)", foot + " ".join(x["attrs"].get("href", "") for x in self.home["p"].anchors))
        a.add("F05", "Footer: telefono (se rilevante)", "ok" if tel else "warn", tel.group(0) if tel else "assente (non obbligatorio)")
        legal_links = {k: any(re.search(k, x["attrs"].get("href", ""), re.I) for x in self.home["p"].anchors) for k in ("privacy", "termin|condizion|terms", "cookie")}
        a.add("F06", "Footer: link a Privacy, Termini, Cookie", "ok" if all(legal_links.values()) else "fail", str(legal_links))
        rea = re.search(r"\bREA\b[^\d]{0,6}[\w ]{0,8}\d+|registro imprese|capitale sociale[^A-Za-z]{0,30}[\d.,]+(?:\s*i\.?v\.?)?", fl, re.I)
        a.add("F07", "Capitale sociale / REA / Registro Imprese", "ok" if rea else "warn", rea.group(0) if rea else "non trovati (consigliati per le società)")
        # H
        rnd = f"/zz-go-live-test-{random.Random().randint(10000, 99999)}"
        r404 = self.http.fetch(self.url(rnd))
        body404 = Http.text(r404)
        t404 = parse_html(body404)
        custom = bool(t404.title and (self.cfg["name"].split(".")[0].lower() in t404.title.lower() or t404.headings))
        if r404["status"] == 404:
            a.add("H01", "Pagina 404 personalizzata (e status 404 reale)", "ok" if custom else "warn", f"404 con titolo '{short(t404.title, 60)}'")
        elif r404["status"] == 200:
            a.add("H01", "Pagina 404 personalizzata (e status 404 reale)", "fail", "soft-404: un URL inesistente risponde 200")
        else:
            a.add("H01", "Pagina 404 personalizzata (e status 404 reale)", "warn", f"status {r404['status']}")
        a.add("H02", "Pagina di errore 500 personalizzata", "manual", "non provocabile senza fare danni")
        hp = self.home["p"]
        icon = hp.link_rel("icon") or hp.link_rel("shortcut")
        apple = hp.link_rel("apple-touch-icon")
        manifest = hp.link_rel("manifest")
        fav = self.asset(self.url("/favicon.ico"))
        a.add("H03", "Favicon, apple-touch-icon e manifest", "ok" if (icon or fav["status"] == 200) and apple and manifest else "warn",
              f"icon: {len(icon)} (favicon.ico {fav['status']}); apple-touch-icon: {len(apple)}; manifest: {len(manifest)}")
        year = re.search(r"(?:©|&copy;|copyright)\s*(?:\(c\))?\s*((?:19|20)\d\d)", foot, re.I)
        now = dt.date.today().year
        a.add("H05", "Copyright con anno aggiornato", "warn" if (not year or int(year.group(1)) < now) else "ok",
              f"anno {year.group(1)} (corrente {now})" if year else "nessun © con anno nel footer")
        ogu = hp.meta("og:image", "property")
        if ogu:
            r = self.asset(urllib.parse.urljoin(self.base + "/", ogu), maxbytes=3_000_000)
            sz = image_size(r["body"]) if r["ok"] else None
            ok_dim = bool(sz and sz[0] >= 1200 and sz[1] >= 630)
            a.add("H04", "og:image raggiungibile, ≥ 1200×630, formato supportato", "ok" if (r["status"] == 200 and ok_dim) else ("warn" if r["status"] == 200 else "fail"),
                  f"status {r['status']}; {sz[0]}×{sz[1]} {sz[2]}; {r['raw_len'] / 1024:.0f} kB" if sz else f"status {r['status']}; dimensioni non leggibili")
        else:
            a.add("H04", "og:image raggiungibile, ≥ 1200×630, formato supportato", "fail", "og:image assente")
        for cid, t in (("H06", "Homepage ottimizzata per la keyword primaria"), ("H07", "Landing principali completate"), ("H08", "Competition analysis e strategia long-tail")):
            a.add(cid, t, "manual", "valutazione editoriale")
        # R: E-E-A-T
        pth, _ = self.first_ok(lg["about_paths"])
        a.add("R01", "Pagina Chi siamo / About accessibile", "ok" if pth else "fail", pth or "nessuna tra " + ", ".join(lg["about_paths"]))
        org = None
        for raw in hp.jsonld:
            try:
                data = json.loads(raw)
            except Exception:
                continue
            nodes = data if isinstance(data, list) else data.get("@graph", [data]) if isinstance(data, dict) else []
            for n in nodes:
                if isinstance(n, dict) and str(n.get("@type", "")) in ("Organization", "Corporation", "LocalBusiness", "NewsMediaOrganization"):
                    org = n
        for cid, key, title in (("R02", "contactPoint", "Schema Organization: contactPoint"), ("R03", "sameAs", "Schema Organization: sameAs (profili social)"),
                                ("R04", "address", "Schema Organization: address"), ("R05", "logo", "Schema Organization: logo")):
            a.add(cid, title, "na" if org is None else ("ok" if org.get(key) else "warn"),
                  "nessuna Organization nel JSON-LD della home" if org is None else (f"presente: {short(json.dumps(org.get(key), ensure_ascii=False), 80)}" if org.get(key) else "assente"))
        eth = bool(org and org.get("ethicsPolicy")) or any(re.search(r"editorial|etic|metodolog|linee-guida|policy-editoriale", x["attrs"].get("href", ""), re.I) for x in hp.anchors)
        a.add("R06", "Policy editoriale / ethicsPolicy dichiarata", "ok" if eth else "warn", "trovata" if eth else "non trovata (peso maggiore per contenuti YMYL: salute, finanza, energia)")
        art = [pg for pg in self.okpages if any(t in (json.dumps(pg["p"].jsonld) if pg["p"].jsonld else "") for t in ("Article", "BlogPosting", "NewsArticle"))]
        if art:
            no_auth = [urllib.parse.urlsplit(pg["url"]).path for pg in art if '"author"' not in " ".join(pg["p"].jsonld)]
            no_date = [urllib.parse.urlsplit(pg["url"]).path for pg in art if "datePublished" not in " ".join(pg["p"].jsonld)]
            a.add("R07", "Articoli: autore e date in Schema.org", "warn" if (no_auth or no_date) else "ok",
                  f"{len(art)} articoli; senza autore: {no_auth[:3]}; senza data: {no_date[:3]}")
        else:
            a.add("R07", "Articoli: autore e date in Schema.org", "na", "nessun Article nelle pagine campionate")
        for cid, t in (("R08", "Pagine autore con bio e profilo"), ("R09", "Citazioni da fonti autorevoli, Wikidata/Wikipedia, trust badge")):
            a.add(cid, t, "manual", "valutazione manuale")
        # O: backup
        for cid, t in (("O01", "Backup automatici (file + database)"), ("O02", "Frequenza adeguata"), ("O03", "Rollback documentato e testato"), ("O04", "Copie off-site")):
            a.add(cid, t, "manual", "non verificabile dall'esterno")

    # ---------------------------------------------------------------- S: coerenza tra fonti
    def run_S(self):
        a, cfg = self.a, self.cfg
        priv = self.legal_text.get("privacy_paths", "")
        cook = self.legal_text.get("cookie_paths", "")
        terms = self.legal_text.get("terms_paths", "")
        corpus = priv + " " + cook + " " + terms
        em = cfg["email"]
        # fornitori email rilevati dal DNS
        spf = " ".join(a.facts.get("spf", []))
        mx = " ".join(a.facts.get("mx", []))
        dkim = " ".join(a.facts.get("dkim_found", []))
        prov_status = {}
        names = set(em["providers"]) & set(MAIL_PROVIDERS)
        for key, (name, inc, sels, mxt, al) in MAIL_PROVIDERS.items():
            if key in names or any(re.search(r"\b" + re.escape(x) + r"\b", priv, re.I) for x in al[:1]) and key in ("resend", "amazonses", "sendgrid", "mailgun", "postmark", "brevo", "mailchimp"):
                spf_ok = any(i in spf for i in inc)
                mx_ok = any(t in mx for t in mxt)
                dk_ok = any(s in dkim for s in sels) if sels else None
                if key == "resend":
                    r1, _ = doh_values(f"send.{self.domain}", "MX")
                    spf_ok = spf_ok or bool(r1["answers"])
                prov_status[name] = {"spf_or_mx": spf_ok or mx_ok, "dkim": dk_ok, "declared": key in names, "in_privacy": any(re.search(r"\b" + re.escape(x) + r"\b", priv, re.I) for x in al)}
        a.facts["mail_providers"] = prov_status
        if not prov_status:
            a.add("K01", "Provider email dichiarati (config/privacy)", "na", "nessun provider email dichiarato in [email].providers né citato nella privacy")
        else:
            a.add("K01", "Provider email dichiarati (config/privacy)", "ok", ", ".join(f"{n} ({'config' if v['declared'] else ''}{'+' if v['declared'] and v['in_privacy'] else ''}{'privacy' if v['in_privacy'] else ''})" for n, v in prov_status.items()))
        bad = [n for n, v in prov_status.items() if not v["spf_or_mx"]]
        crit = "P0" if em["auth_via_email"] else None
        a.add("K02", "SPF/MX coprono tutti i mittenti dichiarati", "na" if not prov_status else ("fail" if bad else "ok"),
              (f"NON coperti dal DNS: {', '.join(bad)} — se inviano dal dominio SPF fallisce; se non lo usano più, rimuoverli dalla privacy" if bad else "tutti i provider dichiarati hanno traccia in SPF/MX"), crit if bad else None)
        nodk = [n for n, v in prov_status.items() if v["dkim"] is False]
        a.add("K03", "DKIM pubblicato per i provider dichiarati", "na" if not prov_status else ("warn" if nodk else "manual"),
              (f"selettore atteso non trovato per: {', '.join(nodk)}" if nodk else "selettori non verificabili da fuori per alcuni provider (SES, Qboxmail): controllare nelle console"), crit if nodk else None)
        for cid, t in (("K04", "From reale e monitorato, Reply-To corretto"), ("K05", "Test mail-tester.com e Gmail (SPF: PASS, DKIM: PASS)")):
            a.add(cid, t, "manual", "richiede invio di una mail di prova")
        if em["auth_via_email"]:
            a.notes.append("L'autenticazione del prodotto è via email (magic link/OTP): SPF e DKIM sono P0.")
        # S01: sub-responsabili
        required = {}
        for name, v in self.vendors_detected.items():
            required[name] = (v["aliases"], v["why"] + (": " + ", ".join(sorted(set(v["hosts"]))[:3]) if v["hosts"] else ""))
        for i in spf.split():
            for key, (name, inc, _, _, al) in MAIL_PROVIDERS.items():
                if any(x in i for x in inc) and key != "google":
                    required.setdefault(name, (al, "incluso nello SPF"))
        for h in a.facts.get("mx", []):
            for key, (name, _, _, mxt, al) in MAIL_PROVIDERS.items():
                if any(t in h for t in mxt):
                    required.setdefault(name, (al, f"MX {h}"))
        for name in cfg["legal"]["expected_subprocessors"]:
            required.setdefault(name, ([name], "indicato in [legal].expected_subprocessors"))
        for name, v in prov_status.items():
            if v["declared"]:
                required.setdefault(name, ([name], "dichiarato in [email].providers"))
        if not priv:
            a.add("S01", "Elenco sub-responsabili nella privacy = fornitori realmente in uso", "manual", "privacy non leggibile")
        else:
            missing = [(n, why) for n, (al, why) in required.items() if not any(re.search(r"\b" + re.escape(x) + r"\b", corpus, re.I) for x in al)]
            a.add("S01", "Elenco sub-responsabili nella privacy = fornitori realmente in uso", "fail" if missing else "ok",
                  ("fornitori rilevati ma NON citati in privacy/cookie/termini: " + "; ".join(f"{n} ({w})" for n, w in missing) + ". Un'omissione nasconde all'interessato chi tratta i suoi dati (art. 28 GDPR): allineare con un legale") if missing
                  else f"tutti i {len(required)} fornitori rilevati sono citati: {', '.join(sorted(required))}")
        cited_not_seen = []
        for key, (name, inc, _, _, al) in MAIL_PROVIDERS.items():
            if name not in required and any(re.search(r"\b" + re.escape(al[0]) + r"\b", priv, re.I) for _ in [0]) and key in ("resend", "sendgrid", "mailgun", "postmark", "brevo", "mailchimp", "amazonses"):
                cited_not_seen.append(name)
        a.add("S02", "Fornitori citati nella privacy ma non rilevabili dall'esterno", "warn" if cited_not_seen else "ok",
              (", ".join(cited_not_seen) + ": verificare che siano ancora in uso") if cited_not_seen else "nessuno tra quelli noti")
        # S03: P.IVA coerente
        pvs = {}
        for k, t in (("footer", self.home["p"].footer()), ("privacy", priv), ("cookie", cook), ("termini", terms)):
            m = re.findall(r"(?:P\.?\s*IVA|partita iva|VAT)[^\d]{0,15}((?:IT)?\s?\d{11})", t, re.I)
            if m:
                pvs[k] = re.sub(r"\D", "", m[0])
        vals = set(pvs.values())
        exp = cfg["legal"].get("vat")
        bad_vat = len(vals) > 1 or (exp and vals and vals != {re.sub(r"\D", "", exp)})
        a.add("S04", "P.IVA coerente tra footer, privacy, cookie, termini (e configurazione)", "fail" if bad_vat else ("na" if not vals else "ok"),
              "; ".join(f"{k}: {v}" for k, v in pvs.items()) or "nessuna P.IVA trovata")
        # S05: cookie impostati vs cookie policy
        ck = a.facts.get("cookies_first_response", [])
        undocumented = [c for c in ck if cook and c.lower() not in cook.lower()]
        a.add("S05", "Cookie impostati dal server citati nella cookie policy", "na" if not ck else ("warn" if undocumented else "ok"),
              f"non citati: {undocumented}" if undocumented else f"{len(ck)} cookie, tutti citati" if ck else "nessun cookie")
        un = a.facts.get("third_party_unclassified", [])
        a.add("S06", "Domini terzi non classificati (da valutare come possibili sub-responsabili)", "warn" if un else "ok",
              ", ".join(un[:15]) + (" …" if len(un) > 15 else "") if un else "nessuno")

    # ---------------------------------------------------------------- esecuzione
    def _safe(self, fn):
        """Un errore interno in una sezione non deve fermare le altre né passare per 'ok'."""
        try:
            fn()
        except Exception as e:  # noqa: BLE001
            import traceback
            tb = traceback.format_exc().strip().splitlines()[-3:]
            self.a.add("Z00", f"Errore interno del raccoglitore in {fn.__name__}", "manual",
                       f"{type(e).__name__}: {e} | {' / '.join(x.strip() for x in tb)} — i controlli di quella sezione NON sono stati eseguiti")

    def run_isagentic(self):
        """Passo OPZIONALE: legge l'ultimo report pubblico di Is Agentic (is-agentic.com, Vercel su motore Ora) via
        GET /api/v1/report?url=… È SOLA LETTURA: non avvia scansioni (non esiste un'API per farlo; si rilancia dalla pagina web).
        Il dominio viene inviato a is-agentic.com. Il punteggio esclude i controlli non applicabili: adatto ai siti di contenuti."""
        a, cfg = self.a, self.cfg["agent"]
        a.notes.append(f"Passo opzionale Is Agentic attivo: il dominio {self.domain} è stato inviato a is-agentic.com "
                       f"(lettura dell'ultimo report, nessuna scansione avviata).")
        print(f"[isagentic] lettura del report di {self.domain} da is-agentic.com…", file=sys.stderr)
        r = self.http.fetch("https://is-agentic.com/api/v1/report?url=" + urllib.parse.quote(self.domain, safe=""),
                            headers={"Accept": "application/json"})
        body = Http.text(r) if r["body"] else ""
        if r["status"] == 404:
            a.add("Y01", "Punteggio Is Agentic", "manual",
                  "nessun report pubblico per questo dominio: avviare una scansione da https://is-agentic.com/ e rilanciare")
            return
        if r["status"] == 429:
            a.add("Z04", "Passo Is Agentic non eseguito", "manual", "quota dell'API pubblica esaurita (120 richieste/min per IP): riprovare")
            return
        try:
            d = json.loads(body[body.index("{"):])
            score = d["score"]
        except Exception:
            a.add("Z04", "Passo Is Agentic non eseguito", "manual",
                  f"status {r['status']}: " + short((r.get("error") or body or "risposta non leggibile").replace("\n", " "), 200))
            return
        bd = d.get("score_breakdown", {})
        parts = []
        for tier in ("essential", "recommended"):
            t = bd.get(tier)
            if t:
                parts.append(f"{tier} {t.get('earned')}/{t.get('available')} ({t.get('passing')}/{t.get('total')} controlli)")
        if bd.get("bonus"):
            parts.append(f"bonus +{bd['bonus'].get('points')}")
        age_txt, stale = "", False
        try:
            when = dt.datetime.fromisoformat(d["scanned_at"].replace("Z", "+00:00"))
            hours = (dt.datetime.now(dt.timezone.utc) - when).total_seconds() / 3600
            age_txt = f"scansione di {hours:.0f} h fa" if hours < 48 else f"scansione di {hours / 24:.0f} giorni fa"
            stale = hours > float(cfg.get("isagentic_max_age_h", 24))
        except Exception:
            pass
        ev = (f"{score}/100 «{d.get('score_label', '')}»; {'; '.join(parts)}; {d.get('eligible_checks', '?')} controlli applicabili; "
              f"{age_txt}{' — POSSIBILMENTE OBSOLETA: dopo modifiche al sito rilanciare la scansione da is-agentic.com' if stale else ''}. "
              f"Report: {d.get('report_url', '')}")
        thr = cfg.get("isagentic_min_score")
        if thr is None:
            a.add("Y01", "Punteggio Is Agentic (informativo)", "manual", ev)
        else:
            a.add("Y01", f"Punteggio Is Agentic ≥ {thr}", "ok" if score >= thr else "warn", ev, "P2" if score < thr else None)
        for it in d.get("issues", []):
            tier, res = it.get("tier"), it.get("result")
            status = "fail" if tier == "essential" and res == "failed" else "warn"
            prio = {"essential": "P1", "recommended": "P2"}.get(tier, "P3")
            a.add(f"Y-{it.get('id')}", f"Is Agentic ({tier}, {res}): {it.get('name')}", status,
                  f"{short(it.get('details', ''), 200)} → {short(it.get('recommendation', ''), 260)}", prio)

    def run_ax(self):
        """Passo OPZIONALE: `npx ax audit <url> --json` (Ora). Invia il dominio al servizio esterno ora.ai e porta nel report il
        punteggio e i 'top fix' come 🔲 (parere esterno, pensato per prodotti con API: non altera ✅/⚠️/❌).
        Con [agent].ax_min_score il punteggio diventa un controllo (✅/⚠️)."""
        import subprocess
        import tempfile
        cfg, a = self.cfg["agent"], self.a
        pkg = cfg.get("ax_package") or "ax@0.10.1"
        cmd = ["npx", "--yes", pkg, "audit", self.base, "--json"]
        if cfg.get("ax_force"):
            cmd.append("--force")
        a.notes.append(f"Passo opzionale ax attivo: il dominio {self.domain} è stato inviato al servizio Ora (ora.ai) per la scansione.")
        print(f"[ax] invio di {self.domain} a ora.ai ({pkg})…", file=sys.stderr)
        env = {k: v for k, v in os.environ.items() if not k.startswith(("ORA_",))}  # nessuna chiave/tunnel implicito
        try:
            r = subprocess.run(cmd, cwd=tempfile.mkdtemp(prefix="golive-ax-"), env=env, capture_output=True, text=True, timeout=240)
        except FileNotFoundError:
            a.add("Z03", "Passo ax non eseguito", "manual", "npx non trovato: installare Node.js")
            return
        except subprocess.TimeoutExpired:
            a.add("Z03", "Passo ax non eseguito", "manual", "timeout (240 s)")
            return
        out = r.stdout
        try:
            d = json.loads(out[out.index("{"):])
        except Exception:
            a.add("Z03", "Passo ax non eseguito", "manual",
                  f"exit {r.returncode}: " + short((r.stderr or out or "nessun output").strip().replace("\n", " "), 200))
            return
        score, grade, rep = d.get("score"), d.get("grade"), d.get("url", "")
        layers = ", ".join(f"{L['name']} {L['score']}/{L['maxScore']}" for L in d.get("layers", []) if L.get("maxScore"))
        fails = sum(1 for L in d.get("layers", []) for c in L["checks"] if c.get("status") == "fail" and not c.get("bonus"))
        ev = (f"{score}/100 (grado {grade}); {layers}; {fails} controlli non-bonus falliti. "
              f"Il modello è pensato per prodotti con API/MCP/OAuth: molti controlli non riguardano siti di contenuti. Report: {rep}")
        thr = cfg.get("ax_min_score")
        if thr is None:
            a.add("X01", "Punteggio Ora ax (informativo)", "manual", ev + " — impostare [agent].ax_min_score per trasformarlo in un controllo")
        else:
            a.add("X01", f"Punteggio Ora ax ≥ {thr}", "ok" if score is not None and score >= thr else "warn", ev)
        for f in (d.get("topFixes") or [])[: int(cfg.get("ax_top", 6))]:
            a.add(f"X-{f['id']}", f"ax: {f['name']}" + (" (bonus)" if f.get("bonus") else ""), "manual",
                  f"≈ +{f.get('estScoreGain', '?')} pt stimati da Ora. {short(f.get('recommendation', ''), 330)}")

    def run_browser(self):
        """Modulo browser (Playwright + axe-core + Lighthouse) in un processo separato; unisce i controlli."""
        import subprocess
        import tempfile
        bc = self.cfg["browser"]
        py = bc.get("python") or os.path.join(SKILL_DIR, ".venv", "bin", "python")
        if not os.path.exists(py):
            self.a.add("Z02", "Modulo browser non eseguito", "manual",
                       f"interprete con Playwright non trovato ({py}): creare .venv nella cartella della skill e installare 'playwright'")
            return
        tmp = tempfile.mkdtemp(prefix="golive-")
        pol = os.path.join(tmp, "policy.txt")
        open(pol, "w").write(" ".join(self.legal_text.get(k, "") for k in ("cookie_paths", "privacy_paths")))
        paths = []
        for u in self.sample:
            pg = self.pages.get(u)
            if pg and pg["p"] and pg["res"]["status"] == 200:
                paths.append(urllib.parse.urlsplit(u).path or "/")
        paths = list(dict.fromkeys(paths))[: max(1, int(bc["pages"]))]
        out = os.path.join(tmp, "browser.json")
        shots = os.path.join(self.cfg.get("_outdir", tmp), "shots")
        cmd = [py, os.path.join(SKILL_DIR, "scripts", "browser.py"), "--url", self.base, "--pages", ",".join(paths),
               "--out", out, "--policy-text", pol, "--shots", shots]
        axe = os.path.join(SKILL_DIR, "node_modules", "axe-core", "axe.min.js")
        if os.path.exists(axe):
            cmd += ["--axe", axe]
        lh = os.path.join(SKILL_DIR, "node_modules", ".bin", "lighthouse")
        chromes = sorted(glob.glob(os.path.expanduser("~/.cache/ms-playwright/chromium-*/chrome-linux*/chrome")))
        if bc["lighthouse"] and os.path.exists(lh) and chromes:
            cmd += ["--lighthouse", lh, "--chrome", chromes[-1]]
        if not bc["mobile"]:
            cmd.append("--no-mobile")
        t0 = time.time()
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
        except Exception as e:
            self.a.add("Z02", "Modulo browser non eseguito", "manual", f"{type(e).__name__}: {e}")
            return
        if not os.path.exists(out):
            self.a.add("Z02", "Modulo browser non eseguito", "manual", short(r.stderr[-400:] or r.stdout[-400:], 400))
            return
        data = json.load(open(out))
        new = {c["id"]: c for c in data["checks"]}
        self.a.checks = [c for c in self.a.checks if c["id"] not in new]
        if any(i in new for i in ("G08b", "G07m", "G07d")):
            self.a.checks = [c for c in self.a.checks if c["id"] not in ("G07", "G08", "G09", "G10")]
        self.a.checks += list(new.values())
        self.a.facts["browser_seconds"] = round(time.time() - t0, 1)
        self.a.facts["browser_pages"] = paths

    def run(self):
        self._safe(self.run_A)
        if not (self.home and self.home["p"]):
            r = self.home["res"] if self.home else {}
            self.a.add("A00", "Homepage raggiungibile e in HTML", "fail",
                       f"status {r.get('status')}, errore {r.get('error')}", "P0")
            self.a.notes.append("Homepage non raggiungibile: i controlli successivi sono stati saltati "
                                "(un controllo non eseguito non è un controllo superato).")
            self.finish()
            return self.a
        self._safe(self.run_B)
        self._safe(self.run_C_D)
        self._safe(self.choose_sample)
        self._safe(self.collect_third_parties)
        self._safe(self.run_pages)
        self._safe(self.run_M)
        self._safe(self.run_assets)
        self._safe(self.run_legal_company)
        self._safe(self.collect_third_parties)
        self._safe(self.run_S)
        if self.cfg["browser"]["enabled"]:
            self._safe(self.run_browser)
        if self.cfg["agent"].get("isagentic"):
            self._safe(self.run_isagentic)
        if self.cfg["agent"].get("ax"):
            self._safe(self.run_ax)
        self.finish()
        return self.a

    def finish(self):
        ign = self.cfg["ignore"]["checks"]
        for c in self.a.checks:
            if any(fnmatch.fnmatch(c["id"], g) for g in ign):
                c["status"], c["evidence"] = "na", "ignorato da configurazione (" + c["evidence"][:100] + ")"
            if not c["prio"]:
                fp = PRIO.get(c["id"], ("P1", "P2"))
                c["prio"] = fp[0] if c["status"] == "fail" else fp[1] if c["status"] == "warn" else ("P3" if c["status"] == "manual" else None)
        self.a.facts["requests"] = self.http.requests
        self.a.facts["seconds"] = round(time.time() - self.t0, 1)


# =========================================================================== output
def summarize(checks):
    s = {k: 0 for k in ICON}
    for c in checks:
        s[c["status"]] += 1
    return s


def diff_with_previous(cur, prev):
    if not prev:
        return None
    old = {c["id"]: c for c in prev["checks"]}
    order = {"fail": 0, "warn": 1, "manual": 2, "ok": 3, "na": 4}
    reg, imp, new, neutral = [], [], [], []
    for c in cur["checks"]:
        o = old.get(c["id"])
        if not o:
            new.append(c["id"])
        elif o["status"] != c["status"]:
            line = f"{c['id']} {c['title']}: {ICON[o['status']]} → {ICON[c['status']]}"
            if "na" in (o["status"], c["status"]):  # 'non applicabile' <-> altro: cambia il perimetro, non la qualità
                neutral.append(line)
            else:
                (reg if order[c["status"]] < order[o["status"]] else imp).append(line)
    return {"previous": prev["generated"], "regressions": reg, "improvements": imp, "new_checks": new, "neutral": neutral}


def render_md(res, delta):
    L = []
    s = res["summary"]
    cfg = res["config"]
    L.append("━" * 55)
    L.append(f"🚀 **GO-LIVE CHECKLIST — {cfg['name']}** (raccolta automatica v{VERSION})")
    L.append(f"URL: {cfg['url']} | Data: {res['generated']} | Pagine campione: {res['facts'].get('pages_ok')} | Richieste: {res['facts'].get('requests')} | Durata: {res['facts'].get('seconds')}s")
    L.append("━" * 55)
    for note in res["notes"]:
        L.append(f"> ℹ️ {note}")
    by = {}
    for c in res["checks"]:
        by.setdefault(c["cat"], []).append(c)
    for cat in CATS:
        if cat not in by:
            continue
        L.append(f"\n### {cat}. {CATS[cat]}")
        for c in sorted(by[cat], key=lambda x: x["id"]):
            pr = f" **[{c['prio']}]**" if c["prio"] in ("P0", "P1") and c["status"] in ("fail", "warn") else ""
            L.append(f"- {ICON[c['status']]} `{c['id']}` {c['title']}{pr} — {c['evidence']}")
    tot = sum(v for k, v in s.items() if k != "na")
    L.append("\n" + "━" * 55)
    L.append(f"**SCORE:** {s['ok']}✅ / {tot} verificabili · {s['fail']}❌ · {s['warn']}⚠️ · {s['manual']}🔲 manuali · {s['na']}➖ non applicabili _(conteggi calcolati dallo script)_")
    for p, label in (("P0", "🔴 P0 — CRITICI (bloccano il lancio)"), ("P1", "🟡 P1 — ALTA PRIORITÀ"), ("P2", "🟢 P2 — OTTIMIZZAZIONE"), ("P3", "⚪ P3 — BACKLOG / VERIFICHE MANUALI")):
        items = [c for c in res["checks"] if c["prio"] == p and c["status"] in (("fail", "warn") if p != "P3" else ("manual",))]
        if p == "P0":
            items = [c for c in res["checks"] if c["prio"] == "P0" and c["status"] in ("fail", "warn")]
        if not items:
            continue
        L.append(f"\n### {label}")
        for c in items:
            L.append(f"- {ICON[c['status']]} `{c['id']}` {c['title']} — {short(c['evidence'], 220)}")
    if delta:
        L.append(f"\n### 🔁 Variazioni rispetto all'esecuzione del {delta['previous']}")
        for k, lab in (("regressions", "Peggiorati"), ("improvements", "Migliorati")):
            if delta[k]:
                L.append(f"- **{lab}:** " + "; ".join(delta[k][:15]))
        if delta.get("neutral"):
            L.append("- **Perimetro cambiato (non applicabile ↔ verificato):** " + "; ".join(delta["neutral"][:10]))
        if not delta["regressions"] and not delta["improvements"] and not delta.get("neutral"):
            L.append("- nessuna variazione di stato")
    L.append("\n_Solo richieste in lettura. I punti 🔲 richiedono browser reale, accessi (Search Console, GA4) o revisione umana. I punti legali sono segnalazioni tecniche, non giudizi legali._")
    return "\n".join(L)


def build_alert(res, delta, cfg, report_path):
    """Testo dell'avviso e decisione se inviarlo. mode='changes': solo se qualcosa peggiora, scade il certificato
    o è la prima esecuzione; mode='always': sempre."""
    s = res["summary"]
    tot = sum(v for k, v in s.items() if k != "na")
    p0 = [c for c in res["checks"] if c["prio"] == "P0" and c["status"] in ("fail", "warn")]
    reg = (delta or {}).get("regressions", [])
    imp = (delta or {}).get("improvements", [])
    tls = res["facts"].get("tls", {})
    days = tls.get("days_left") if tls.get("ok") else None
    cert_low = days is not None and days < cfg["notify"]["cert_days_warn"]
    send = bool(reg) or cert_low or delta is None or cfg["notify"]["mode"] == "always"
    L = [f"go-live: {cfg['name']} — {res['generated']}",
         f"Score {s['ok']}✅/{tot} · {s['fail']}❌ · {s['warn']}⚠️ · {s['manual']}🔲"]
    if p0:
        L.append(f"P0 aperti ({len(p0)}): " + "; ".join(f"{c['id']} {short(c['title'], 45)}" for c in p0[:6]))
    if reg:
        L.append(f"PEGGIORATI ({len(reg)}): " + "; ".join(reg[:8]))
    if imp:
        L.append(f"Migliorati: {len(imp)}")
    if cert_low:
        L.append(f"⚠️ Certificato HTTPS: scade tra {days} giorni")
    if delta is None:
        L.append("(prima esecuzione: nessun confronto)")
    L.append(f"Report: {report_path}")
    return send, "\n".join(L)[:3800]


def notify(res, delta, cfg, report_path):
    import urllib.request
    send, text = build_alert(res, delta, cfg, report_path)
    outdir = cfg["_outdir"]
    status = os.path.join(outdir, "last-notify.txt")
    if not send:
        open(status, "w").write(f"{res['generated']} nessun avviso (nessun peggioramento)\n")
        print("[notify] nessun avviso da inviare", file=sys.stderr)
        return
    envf = os.path.expanduser(cfg["notify"]["telegram_env"])
    tok = chat = None
    if os.path.exists(envf):
        for line in open(envf):
            k, _, v = line.strip().partition("=")
            if k == "TELEGRAM_BOT_TOKEN":
                tok = v.strip().strip('"')
            elif k == "TELEGRAM_CHAT_ID":
                chat = v.strip().strip('"')
    if not (tok and chat):
        open(status, "w").write(f"{res['generated']} AVVISO NON INVIATO: manca {envf} (TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)\n{text}\n")
        print(f"[notify] avviso non inviato: configurazione Telegram assente ({envf})\n{text}", file=sys.stderr)
        return
    data = urllib.parse.urlencode({"chat_id": chat, "text": text, "disable_web_page_preview": "true"}).encode()
    try:
        with urllib.request.urlopen(urllib.request.Request(f"https://api.telegram.org/bot{tok}/sendMessage", data=data), timeout=20, context=CTX) as r:
            ok = json.load(r).get("ok")
        open(status, "w").write(f"{res['generated']} avviso inviato: {ok}\n")
        print(f"[notify] avviso Telegram inviato: {ok}", file=sys.stderr)
    except Exception as e:  # il token non deve finire nei log
        msg = str(e).replace(tok, "***")
        open(status, "w").write(f"{res['generated']} INVIO FALLITO: {type(e).__name__}: {msg}\n")
        print(f"[notify] invio fallito: {type(e).__name__}: {msg}", file=sys.stderr)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config")
    ap.add_argument("--url")
    ap.add_argument("--out", default=os.path.expanduser("~/go-live-test"))
    ap.add_argument("--md", action="store_true", help="stampa il report Markdown su stdout")
    ap.add_argument("--no-history", action="store_true")
    ap.add_argument("--browser", action="store_true", help="esegue anche il modulo browser (Playwright/axe/Lighthouse)")
    ap.add_argument("--no-browser", action="store_true")
    ap.add_argument("--isagentic", action="store_true",
                    help="passo OPZIONALE: legge il report di Is Agentic (is-agentic.com, sola lettura). ATTENZIONE: invia il dominio a is-agentic.com")
    ap.add_argument("--ax", action="store_true",
                    help="passo OPZIONALE: scansione Ora `ax` (npx). ATTENZIONE: invia il dominio al servizio esterno ora.ai")
    ap.add_argument("--ax-force", action="store_true", help="con --ax: ignora la cache di Ora (budget 6/giorno)")
    ap.add_argument("--notify", action="store_true", help="invia un avviso Telegram se qualcosa peggiora (vedi [notify])")
    args = ap.parse_args()
    cfg = load_config(args.config, args.url)
    if args.browser:
        cfg["browser"]["enabled"] = True
    if args.no_browser:
        cfg["browser"]["enabled"] = False
    if args.isagentic:
        cfg["agent"]["isagentic"] = True
    if args.ax or args.ax_force:
        cfg["agent"]["ax"] = True
    if args.ax_force:
        cfg["agent"]["ax_force"] = True
    cfg["_outdir"] = os.path.join(args.out, cfg["domain"])
    col = Collector(cfg)
    audit = col.run()
    now = dt.datetime.now().astimezone()
    res = {"version": VERSION, "generated": now.strftime("%Y-%m-%d %H:%M"), "config": {k: cfg[k] for k in ("name", "url", "domain")},
           "summary": summarize(audit.checks), "checks": audit.checks, "facts": audit.facts, "notes": audit.notes}
    outdir = os.path.join(args.out, cfg["domain"])
    os.makedirs(outdir, exist_ok=True)
    prev = None
    files = sorted(glob.glob(os.path.join(outdir, "*.json")))
    if files and not args.no_history:
        try:
            prev = json.load(open(files[-1]))
        except Exception:
            prev = None
    delta = diff_with_previous(res, prev)
    res["delta"] = delta
    stamp = now.strftime("%Y%m%d-%H%M")
    jp = os.path.join(outdir, f"{stamp}.json")
    with open(jp, "w") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    md = render_md(res, delta)
    with open(os.path.join(outdir, f"{stamp}.md"), "w") as f:
        f.write(md)
    if args.notify:
        notify(res, delta, cfg, os.path.join(outdir, f"{stamp}.md"))
    if args.md:
        print(md)
    print(f"\n[json] {jp}", file=sys.stderr)


if __name__ == "__main__":
    main()
