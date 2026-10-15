#!/usr/bin/env python3
"""go-live browser: controlli che richiedono un browser vero (Chromium headless via Playwright) + Lighthouse.

Non modifica nulla sul sito: naviga, osserva, e non invia form. Produce un JSON con controlli nello stesso formato
di collect.py (id, cat, title, status, evidence, prio) che collect.py unisce al report.

Uso: browser.py --url https://dominio --pages /,/guide --out out.json [--axe path/axe.min.js]
                [--policy-text file.txt] [--lighthouse path/al/binario --chrome path/al/chrome] [--shots DIR]
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.parse

from playwright.sync_api import sync_playwright

TRACK_RE = re.compile(
    r"google-analytics\.com|googletagmanager\.com/gtag|analytics\.google\.com|doubleclick\.net|googleadservices|"
    r"facebook\.(net|com)/tr|connect\.facebook\.net|hotjar|clarity\.ms|linkedin\.com/px|snap\.licdn|tiktok\.com/i18n|"
    r"segment\.(io|com)|mixpanel|posthog|plausible|matomo|fullstory|hs-analytics|hubspot|bat\.bing|criteo|taboola|outbrain",
    re.I)
# caricamento di una libreria (normale con Consent Mode: non invia dati) – diverso da un invio di dati (hit)
LIB_RE = re.compile(r"googletagmanager\.com/(gtag/js|gtm\.js|gtag/destination)|google-analytics\.com/analytics\.js|"
                    r"fbevents\.js|static\.hotjar\.com|clarity\.ms/tag|plausible\.io/js", re.I)


def is_hit(u):
    return bool(TRACK_RE.search(u)) and not LIB_RE.search(u)


ANALYTICS_COOKIE = re.compile(r"^(_ga|_gid|_gat|_gcl|_fbp|_fbc|_hj|__utm|ajs_|mp_|_clck|_clsk|_pk_|_uet|_ttp|li_)", re.I)
ACCEPT = re.compile(r"accett|accept|consent|acconsent|va bene|allow all|ok\b|agree", re.I)
REJECT = re.compile(r"rifiut|reject|deny|nega|solo (i )?necessari|only necessary|necessary only|continua senza|decline", re.I)
MANAGE = re.compile(r"person|prefer|gestisc|manage|settings|impostaz|opzioni|customi|scegli", re.I)
SKIP = re.compile(r"salta|skip|vai al contenuto|main content", re.I)

VITALS_JS = """
window.__gl = {lcp:0, cls:0, fcp:0, tbt:0, longtasks:0};
try { new PerformanceObserver(l=>{for(const e of l.getEntries()){window.__gl.lcp=e.startTime}}).observe({type:'largest-contentful-paint',buffered:true}); } catch(e){}
try { new PerformanceObserver(l=>{for(const e of l.getEntries()){if(!e.hadRecentInput)window.__gl.cls+=e.value}}).observe({type:'layout-shift',buffered:true}); } catch(e){}
try { new PerformanceObserver(l=>{for(const e of l.getEntries()){if(e.name==='first-contentful-paint')window.__gl.fcp=e.startTime}}).observe({type:'paint',buffered:true}); } catch(e){}
try { new PerformanceObserver(l=>{for(const e of l.getEntries()){const b=e.duration-50; if(b>0)window.__gl.tbt+=b; window.__gl.longtasks++}}).observe({type:'longtask',buffered:true}); } catch(e){}
"""

CHECKS = []


def add(cid, title, status, evidence="", prio=None):
    CHECKS.append({"id": cid, "cat": cid[0], "title": title, "status": status,
                   "evidence": str(evidence)[:900], "prio": prio})


def short(s, n=140):
    s = re.sub(r"\s+", " ", str(s)).strip()
    return s if len(s) <= n else s[: n - 1] + "…"


def new_ctx(browser, mobile=False):
    if mobile:
        return browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True,
                                   has_touch=True, locale="it-IT",
                                   user_agent="Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 "
                                              "(KHTML, like Gecko) Chrome/120 Mobile Safari/537.36 go-live-audit")
    return browser.new_context(viewport={"width": 1366, "height": 800}, locale="it-IT")


def goto(page, url, timeout=45000):
    page.goto(url, wait_until="load", timeout=timeout)
    try:
        page.wait_for_load_state("networkidle", timeout=15000)
    except Exception:
        pass
    page.wait_for_timeout(2000)


def cookie_names(ctx):
    return sorted({c["name"] for c in ctx.cookies()})


def gcs_state(url):
    """Consent Mode: parametro gcs=G1xy nelle richieste di Google (x = ads, y = analytics; 1 = concesso)."""
    m = re.search(r"[?&]gcs=(G1\d\d)", url)
    return m.group(1) if m else None


def find_buttons(page):
    out = {"accept": None, "reject": None, "manage": None}
    try:
        for b in page.get_by_role("button").all():
            try:
                if not b.is_visible():
                    continue
                t = (b.inner_text(timeout=500) or b.get_attribute("aria-label") or "").strip()
            except Exception:
                continue
            if not t or len(t) > 60:
                continue
            for k, rx in (("reject", REJECT), ("manage", MANAGE), ("accept", ACCEPT)):
                if rx.search(t) and out[k] is None:
                    out[k] = (b, t)
                    break
    except Exception:
        pass
    return out


def find_banner(page):
    sel = ("[role=dialog], [aria-modal=true], [role=alertdialog], [id*=cookie i], [class*=cookie i], "
           "[id*=consent i], [class*=consent i], [id*=gdpr i], [class*=gdpr i]")
    try:
        for el in page.locator(sel).all():
            try:
                if el.is_visible():
                    txt = (el.inner_text(timeout=800) or "").strip()
                    if re.search(r"cookie|consens|privacy|tracciament", txt, re.I) and len(txt) > 20:
                        return el, txt
            except Exception:
                continue
    except Exception:
        pass
    return None, ""


# ------------------------------------------------------------------ consenso
def consent_tests(browser, base, policy_text, shots):
    reqs = []
    ctx = new_ctx(browser)
    page = ctx.new_page()
    page.on("request", lambda r: reqs.append(r.url))
    try:
        goto(page, base + "/")
    except Exception as e:
        add("E04", "Cookie banner presente (browser)", "manual", f"pagina non caricata: {short(e, 120)}")
        ctx.close()
        return
    before = cookie_names(ctx)
    trk_before = [u for u in reqs if is_hit(u)]
    libs_before = [u for u in reqs if LIB_RE.search(u)]
    banner, btxt = find_banner(page)
    btn = find_buttons(page)
    if shots:
        try:
            page.screenshot(path=os.path.join(shots, "banner-desktop.png"))
        except Exception:
            pass
    if banner:
        parts = [f"{k}: «{v[1]}»" if v else f"{k}: —" for k, v in btn.items()]
        add("E04", "Cookie banner presente (browser)", "ok", "banner visibile al primo caricamento; " + "; ".join(parts))
        if btn["accept"] and not btn["reject"]:
            add("E04b", "Banner: «Rifiuta» disponibile al primo livello come «Accetta»", "warn",
                "c'è «Accetta» ma nessun pulsante di rifiuto/solo necessari al primo livello (le linee guida del Garante lo richiedono: segnalazione tecnica, non giudizio legale)")
        else:
            add("E04b", "Banner: «Rifiuta» disponibile al primo livello come «Accetta»", "ok" if btn["reject"] else "manual",
                "presente" if btn["reject"] else "pulsanti non riconosciuti automaticamente")
    else:
        add("E04", "Cookie banner presente (browser)", "fail" if (trk_before or before) else "warn",
            f"nessun banner visibile al primo caricamento; cookie già presenti: {before or 'nessuno'}; richieste di tracciamento: {len(trk_before)}",
            "P0" if (trk_before or any(ANALYTICS_COOKIE.match(c) for c in before)) else None)
    an = [c for c in before if ANALYTICS_COOKIE.match(c)]
    add("E06b", "Nessun cookie di analytics prima del consenso (browser)", "fail" if an else "ok",
        f"cookie analytics già impostati: {an}" if an else f"cookie prima di ogni scelta: {before or 'nessuno'}", "P0" if an else None)
    states = sorted({s for s in (gcs_state(u) for u in trk_before) if s})
    hosts = sorted({urllib.parse.urlsplit(u).hostname for u in trk_before})
    if not trk_before:
        add("E06c", "Invio di dati di tracciamento prima del consenso", "ok",
            f"nessun invio di dati; librerie caricate: {len(libs_before)} (normale con Consent Mode: la libreria non invia dati finché il consenso è negato)")
    elif states and all(s == "G100" for s in states):
        add("E06c", "Invio di dati di tracciamento prima del consenso", "warn",
            f"{len(trk_before)} richieste verso {', '.join(hosts)} con consenso NEGATO (gcs=G100): sono i ping senza cookie del Consent Mode avanzato. "
            "Verificare che la privacy lo dichiari")
    elif any(s in ("G111", "G110", "G101") for s in states):
        add("E06c", "Invio di dati di tracciamento prima del consenso", "fail",
            f"richieste verso {', '.join(hosts)} con consenso CONCESSO prima di ogni scelta (gcs={states})", "P0")
    else:
        add("E06c", "Invio di dati di tracciamento prima del consenso", "warn",
            f"{len(trk_before)} invii verso {', '.join(hosts)} prima di ogni scelta, senza parametro di consenso riconoscibile: verificare nel pannello rete del browser")
    # rifiuto
    if btn["reject"]:
        n0 = len(reqs)
        try:
            btn["reject"][0].click(timeout=3000)
            page.wait_for_timeout(2500)
            after = cookie_names(ctx)
            new = [u for u in reqs[n0:] if is_hit(u)]
            an2 = [c for c in after if ANALYTICS_COOKIE.match(c)]
            ok_g = [u for u in new if gcs_state(u) in ("G111", "G110", "G101")]
            add("E06d", "Dopo «Rifiuta»: nessun cookie né tracciamento con consenso concesso", "fail" if (an2 or ok_g) else "ok",
                f"cookie analytics: {an2 or 'nessuno'}; richieste con consenso concesso: {len(ok_g)}; nuove richieste di tracciamento: {len(new)}",
                "P0" if (an2 or ok_g) else None)
        except Exception as e:
            add("E06d", "Dopo «Rifiuta»: nessun cookie né tracciamento", "manual", f"click non riuscito: {short(e, 100)}")
    else:
        add("E06d", "Dopo «Rifiuta»: nessun cookie né tracciamento", "manual", "pulsante di rifiuto non trovato")
    ctx.close()
    # accettazione in un contesto pulito
    ctx2 = new_ctx(browser)
    p2 = ctx2.new_page()
    reqs2 = []
    p2.on("request", lambda r: reqs2.append(r.url))
    try:
        goto(p2, base + "/")
        b2 = find_buttons(p2)
        if b2["accept"]:
            b2["accept"][0].click(timeout=3000)
            p2.wait_for_timeout(3500)
            names = cookie_names(ctx2)
            ls = p2.evaluate("Object.keys(localStorage)")
            und = [c for c in names if policy_text and c.lower() not in policy_text.lower()]
            add("S05b", "Cookie impostati dopo «Accetta» tutti citati nella cookie policy", "na" if not names else ("warn" if und else "ok"),
                (f"non citati: {und} (su {len(names)}: {names})" if und else f"{len(names)} cookie, tutti citati: {names}") + f"; localStorage: {ls[:6]}")
            hits2 = [u for u in reqs2 if is_hit(u)]
            granted = [u for u in hits2 if gcs_state(u) in ("G111", "G110", "G101")]
            an3 = [c for c in names if ANALYTICS_COOKIE.match(c)]
            add("E06e", "Dopo «Accetta» il tracciamento parte (la scelta ha effetto)", "ok" if (hits2 or an3) else "manual",
                f"{len(hits2)} invii di dati ({len(granted)} con consenso concesso); cookie analytics: {an3 or 'nessuno'}" if (hits2 or an3)
                else "nessun invio né cookie dopo «Accetta» (il tag potrebbe non essere attivo)")
            p2.reload(wait_until="load")
            p2.wait_for_timeout(2500)
            bn, _ = find_banner(p2)
            add("E12", "La scelta del consenso viene ricordata al ricaricamento", "fail" if bn else "ok",
                "il banner ricompare dopo il ricaricamento" if bn else "il banner non ricompare")
        else:
            add("S05b", "Cookie impostati dopo «Accetta» tutti citati nella cookie policy", "manual", "pulsante «Accetta» non trovato")
    except Exception as e:
        add("S05b", "Cookie dopo «Accetta»", "manual", f"errore: {short(e, 120)}")
    ctx2.close()


# ------------------------------------------------------------------ pagine
def audit_pages(browser, base, paths, axe_path, shots):
    console, csp, failed, status4 = [], [], [], []
    vit_d, vit_m = [], []
    axe_all = []
    for i, path in enumerate(paths):
        url = urllib.parse.urljoin(base + "/", path.lstrip("/"))
        ctx = new_ctx(browser)
        page = ctx.new_page()
        page.add_init_script(VITALS_JS)

        def on_console(m, path=path):
            if m.type == "error":
                t = m.text
                (csp if re.search(r"content security policy|refused to", t, re.I) else console).append(f"{path}: {short(t, 160)}")
        page.on("console", on_console)
        page.on("pageerror", lambda e, path=path: console.append(f"{path}: JS: {short(e, 140)}"))
        page.on("requestfailed", lambda r, path=path: None if "ERR_ABORTED" in str(r.failure) else failed.append(f"{path}: {short(r.url, 90)} ({r.failure})"))
        page.on("response", lambda r, path=path: status4.append(f"{path}: {r.status} {short(r.url, 90)}") if r.status >= 400 else None)
        try:
            goto(page, url)
        except Exception as e:
            console.append(f"{path}: navigazione fallita: {short(e, 100)}")
            ctx.close()
            continue
        v = page.evaluate("window.__gl") or {}
        vit_d.append((path, v))
        if i == 0 and shots:
            try:
                page.screenshot(path=os.path.join(shots, "home-desktop.png"), full_page=False)
            except Exception:
                pass
        if axe_path and os.path.exists(axe_path):
            try:
                page.add_script_tag(path=axe_path)
                res = page.evaluate("""() => axe.run(document, {runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21a','wcag21aa','wcag22aa']}})
                    .then(r => r.violations.map(v => ({id:v.id, impact:v.impact, help:v.help, nodes:v.nodes.length})))""")
                axe_all.append((path, res))
            except Exception as e:
                axe_all.append((path, [{"id": "errore-axe", "impact": "info", "help": short(e, 80), "nodes": 0}]))
        if i == 0:
            keyboard_test(page)
        ctx.close()
    # console / CSP / richieste
    add("B13", "Nessun errore CSP in console", "warn" if csp else "ok",
        ("; ".join(csp[:4]) + (f" … (+{len(csp) - 4})" if len(csp) > 4 else "")) if csp else f"{len(paths)} pagine caricate senza violazioni CSP")
    add("B14", "Nessun errore JavaScript in console", "warn" if console else "ok",
        ("; ".join(console[:4]) + (f" … (+{len(console) - 4})" if len(console) > 4 else "")) if console else "nessun errore")
    bad = failed + status4
    add("G11", "Nessuna richiesta fallita o 4xx/5xx durante il caricamento", "warn" if bad else "ok",
        ("; ".join(bad[:5]) + (f" … (+{len(bad) - 5})" if len(bad) > 5 else "")) if bad else "tutte le risorse caricate")
    # vitals (laboratorio, senza throttling)
    if vit_d:
        lcp = max(v.get("lcp", 0) for _, v in vit_d)
        cls = max(v.get("cls", 0) for _, v in vit_d)
        tbt = max(v.get("tbt", 0) for _, v in vit_d)
        worst = max(vit_d, key=lambda x: x[1].get("lcp", 0))[0]
        add("G08b", "LCP < 2.5 s (laboratorio desktop, senza throttling)", "ok" if lcp < 2500 else ("warn" if lcp < 4000 else "fail"),
            f"peggiore {lcp / 1000:.2f}s su {worst} ({len(vit_d)} pagine). Dato di laboratorio dal server jedi, non dato reale degli utenti")
        add("G10b", "CLS < 0.1 (laboratorio)", "ok" if cls < 0.1 else ("warn" if cls < 0.25 else "fail"), f"CLS massimo {cls:.3f}")
        add("G09b", "TBT < 200 ms (proxy di INP, laboratorio)", "ok" if tbt < 200 else ("warn" if tbt < 600 else "fail"),
            f"Total Blocking Time massimo {tbt:.0f} ms; l'INP vero richiede dati reali (CrUX/RUM)")
    # axe
    if axe_all:
        agg = {}
        for path, res in axe_all:
            for v in res:
                a = agg.setdefault(v["id"], {"impact": v["impact"], "help": v["help"], "nodes": 0, "pages": set()})
                a["nodes"] += v["nodes"]
                a["pages"].add(path)
        crit = {k: v for k, v in agg.items() if v["impact"] in ("critical", "serious")}
        lines = [f"{k} [{v['impact']}] {v['nodes']} elementi su {len(v['pages'])} pag. — {short(v['help'], 60)}"
                 for k, v in sorted(agg.items(), key=lambda kv: (kv[1]["impact"] != "critical", kv[1]["impact"] != "serious", -kv[1]["nodes"]))]
        add("I11", "axe-core (WCAG 2.2 AA): nessuna violazione critica/seria", "fail" if crit else ("warn" if agg else "ok"),
            (f"{len(crit)} critiche/serie, {len(agg)} totali su {len(axe_all)} pagine: " + " | ".join(lines[:6])) if agg else f"nessuna violazione su {len(axe_all)} pagine",
            "P1" if crit else None)
        contrast = agg.get("color-contrast")
        add("I12", "Contrasto colori ≥ 4.5:1 (WCAG AA)", "fail" if contrast else "ok",
            f"{contrast['nodes']} elementi su {len(contrast['pages'])} pagine" if contrast else "nessuna violazione di contrasto rilevata da axe",
            "P1" if contrast else None)
    else:
        add("I11", "axe-core (WCAG 2.2 AA)", "manual", "axe.min.js non disponibile")


KEY_JS = """
() => { const e = document.activeElement; if (!e || e === document.body) return null;
  const r = e.getBoundingClientRect(); const cs = getComputedStyle(e);
  const ring = (cs.outlineStyle !== 'none' && parseFloat(cs.outlineWidth) > 0) || (cs.boxShadow && cs.boxShadow !== 'none');
  return {tag: e.tagName.toLowerCase(), text: (e.innerText || e.getAttribute('aria-label') || e.getAttribute('title') || '').trim().slice(0, 40),
          ring: !!ring, visible: r.width > 0 && r.height > 0 && r.bottom > 0 && r.top < innerHeight, top: r.top, href: e.getAttribute('href') || ''}; }
"""


def keyboard_test(page):
    seen, ring_ok, no_ring, stuck = [], 0, [], 0
    last = None
    skip_ok = None
    for i in range(30):
        page.keyboard.press("Tab")
        page.wait_for_timeout(80)
        info = page.evaluate(KEY_JS)
        if not info:
            continue
        key = (info["tag"], info["text"], info["href"])
        if key == last:
            stuck += 1
        last = key
        if i == 0:
            skip_ok = bool(SKIP.search(info["text"]) and info["visible"])
        if info["ring"]:
            ring_ok += 1
        else:
            no_ring.append(f"{info['tag']} «{info['text'] or info['href'][:20]}»")
        seen.append(info)
    if not seen:
        add("I13", "Navigazione da tastiera: il focus si sposta e si vede", "manual", "nessun elemento ha ricevuto il focus con Tab")
        return
    pct = ring_ok * 100 // len(seen)
    st = "ok" if pct >= 90 and stuck < 4 else ("warn" if pct >= 60 else "fail")
    add("I13", "Navigazione da tastiera: il focus si sposta ed è visibile", st,
        f"{len(seen)} elementi raggiunti con Tab; indicatore di focus visibile su {pct}%; senza indicatore: {', '.join(no_ring[:4]) or '—'}; "
        f"ferme consecutive (possibile trappola): {stuck}")
    add("I14", "Skip link visibile al primo Tab", "ok" if skip_ok else "warn",
        f"primo elemento: «{seen[0]['text']}»" + ("" if skip_ok else " — non è uno skip link visibile"))


def mobile_test(browser, base, shots):
    ctx = new_ctx(browser, mobile=True)
    page = ctx.new_page()
    page.add_init_script(VITALS_JS)
    try:
        goto(page, base + "/")
    except Exception as e:
        add("H09", "Layout mobile", "manual", f"pagina non caricata: {short(e, 100)}")
        ctx.close()
        return
    info = page.evaluate("""() => {
      const de = document.documentElement;
      const small = [...document.querySelectorAll('a[href],button,input:not([type=hidden]),select,textarea,[role=button]')]
        .filter(e => { const r = e.getBoundingClientRect(); const cs = getComputedStyle(e);
                       if (!(r.width > 0 && r.height > 0) || cs.visibility === 'hidden') return false;
                       if (r.width <= 2 && r.height <= 2) return false;            // nascosti in modo accessibile (sr-only, skip link)
                       if (e.tagName === 'A' && cs.display === 'inline') return false;  // link in linea nel testo: esenti (WCAG 2.5.8)
                       return r.width < 24 || r.height < 24; })
        .map(e => (e.innerText || e.getAttribute('aria-label') || e.tagName).trim().slice(0, 25));
      const tiny = [...document.querySelectorAll('p,li,span,a,td')].filter(e => e.childNodes.length && parseFloat(getComputedStyle(e).fontSize) < 12 && (e.innerText||'').trim().length > 20).length;
      return {overflow: de.scrollWidth - innerWidth, small: small.length, smallEx: small.slice(0, 5), tiny, vw: innerWidth};
    }""")
    v = page.evaluate("window.__gl") or {}
    add("H09", "Mobile: nessuno scorrimento orizzontale", "fail" if info["overflow"] > 2 else "ok",
        f"larghezza contenuto − viewport = {info['overflow']}px (viewport {info['vw']}px)")
    add("H10", "Mobile: aree di tocco ≥ 24×24 px (WCAG 2.2; esclusi link in linea e nascosti)", "warn" if info["small"] > 3 else "ok",
        f"{info['small']} elementi più piccoli di 24px: {info['smallEx']}" if info["small"] else "nessuno")
    add("H11", "Mobile: testo ≥ 12 px", "warn" if info["tiny"] > 3 else "ok", f"{info['tiny']} elementi con testo < 12px")
    if shots:
        try:
            page.screenshot(path=os.path.join(shots, "home-mobile.png"))
        except Exception:
            pass
    add("G08c", "LCP mobile (laboratorio, senza throttling)", "ok" if v.get("lcp", 0) < 2500 else "warn",
        f"{v.get('lcp', 0) / 1000:.2f}s; CLS {v.get('cls', 0):.3f}; TBT {v.get('tbt', 0):.0f} ms")
    ctx.close()


# ------------------------------------------------------------------ Lighthouse
def lighthouse(binary, chrome, url, preset):
    env = dict(os.environ, CHROME_PATH=chrome)
    cmd = [binary, url, "--output=json", "--output-path=stdout", "--quiet",
           "--only-categories=performance,accessibility,best-practices,seo",
           "--chrome-flags=--headless=new --no-sandbox --disable-gpu", "--max-wait-for-load=45000"]
    if preset == "desktop":
        cmd.append("--preset=desktop")
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=240, env=env)
        data = json.loads(p.stdout)
    except Exception as e:
        return {"error": f"{type(e).__name__}: {short(e, 160)}"}
    cats = {k: round((v.get("score") or 0) * 100) for k, v in data.get("categories", {}).items()}
    au = data.get("audits", {})

    def val(k):
        return au.get(k, {}).get("numericValue")
    return {"scores": cats, "lcp": val("largest-contentful-paint"), "cls": val("cumulative-layout-shift"),
            "tbt": val("total-blocking-time"), "fcp": val("first-contentful-paint"), "si": val("speed-index")}


def run_lighthouse(binary, chrome, url):
    for preset in ("mobile", "desktop"):
        r = lighthouse(binary, chrome, url, preset)
        tag = "mobile" if preset == "mobile" else "desktop"
        if "error" in r:
            for cid, t in (("G07", "Lighthouse Performance"), ("I15", "Lighthouse Accessibility"), ("H12", "Lighthouse Best Practices"), ("P08", "Lighthouse SEO")):
                if not any(c["id"] == cid + tag[0] for c in CHECKS):
                    add(cid + tag[0], f"{t} ≥ 90 ({tag})", "manual", f"Lighthouse non eseguito: {r['error']}")
            continue
        s = r["scores"]
        for cid, key, t in (("G07", "performance", "Lighthouse Performance"), ("I15", "accessibility", "Lighthouse Accessibility"),
                            ("H12", "best-practices", "Lighthouse Best Practices"), ("P08", "seo", "Lighthouse SEO")):
            sc = s.get(key, 0)
            add(cid + tag[0], f"{t} ≥ 90 ({tag}, laboratorio)", "ok" if sc >= 90 else ("warn" if sc >= 50 else "fail"),
                f"punteggio {sc}/100" + (f"; LCP {r['lcp'] / 1000:.2f}s, CLS {r['cls']:.3f}, TBT {r['tbt']:.0f}ms, FCP {r['fcp'] / 1000:.2f}s" if key == "performance" and r.get("lcp") else ""))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--pages", default="/")
    ap.add_argument("--out", required=True)
    ap.add_argument("--axe")
    ap.add_argument("--policy-text")
    ap.add_argument("--lighthouse")
    ap.add_argument("--chrome")
    ap.add_argument("--shots")
    ap.add_argument("--no-mobile", action="store_true")
    args = ap.parse_args()
    base = args.url.rstrip("/")
    paths = [p for p in args.pages.split(",") if p] or ["/"]
    policy = open(args.policy_text).read() if args.policy_text and os.path.exists(args.policy_text) else ""
    if args.shots:
        os.makedirs(args.shots, exist_ok=True)
    t0 = time.time()
    with sync_playwright() as pw:
        br = pw.chromium.launch(headless=True, args=["--no-sandbox"])
        for fn in (lambda: consent_tests(br, base, policy, args.shots),
                   lambda: audit_pages(br, base, paths, args.axe, args.shots),
                   lambda: None if args.no_mobile else mobile_test(br, base, args.shots)):
            try:
                fn()
            except Exception as e:  # una sezione che crasha non passa per ok
                add("Z01", "Errore interno del modulo browser", "manual", f"{type(e).__name__}: {short(e, 200)} — sezione NON eseguita")
        br.close()
    if args.lighthouse and args.chrome and os.path.exists(args.lighthouse):
        run_lighthouse(args.lighthouse, args.chrome, base + "/")
    json.dump({"checks": CHECKS, "seconds": round(time.time() - t0, 1)}, open(args.out, "w"), ensure_ascii=False, indent=1)
    print(f"[browser] {len(CHECKS)} controlli in {time.time() - t0:.0f}s -> {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
