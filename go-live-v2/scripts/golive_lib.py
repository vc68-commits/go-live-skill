"""golive_lib: utilita' di rete e parsing per il raccoglitore go-live (solo libreria standard)."""
import gzip
import json
import re
import socket
import ssl
import struct
import time
import urllib.error
import urllib.parse
import urllib.request
import zlib
from html.parser import HTMLParser

UA = "go-live-collector/2.0 (+audit in sola lettura)"


def _make_ctx():
    """Contesto TLS con verifica attiva. Alcuni Python (es. quello di python.org su macOS) non hanno
    certificati radice caricati: in quel caso si usa il bundle di sistema. La verifica NON viene mai disattivata."""
    import os
    ctx = ssl.create_default_context()
    try:
        if ctx.cert_store_stats().get("x509_ca", 0) == 0:
            for cafile in ("/etc/ssl/cert.pem", "/etc/ssl/certs/ca-certificates.crt", "/etc/pki/tls/certs/ca-bundle.crt"):
                if os.path.exists(cafile):
                    ctx.load_verify_locations(cafile)
                    break
    except Exception:
        pass
    return ctx


CTX = _make_ctx()


# --------------------------------------------------------------------------- HTTP
class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


class Http:
    """Client HTTP cortese: ritardo minimo tra richieste allo stesso host, nessuna dipendenza esterna."""

    def __init__(self, delay=1.0, timeout=20):
        self.delay = delay
        self.timeout = timeout
        self.last = 0.0
        self.requests = 0
        https = urllib.request.HTTPSHandler(context=CTX)
        self._follow = urllib.request.build_opener(https)
        self._nofollow = urllib.request.build_opener(https, _NoRedirect)

    def _wait(self):
        dt = time.time() - self.last
        if dt < self.delay:
            time.sleep(self.delay - dt)
        self.last = time.time()

    def fetch(self, url, follow=True, method="GET", headers=None, maxbytes=3_000_000, polite=True):
        """Ritorna un dict: ok, url, final_url, status, headers (minuscole), set_cookie (lista),
        body (bytes, decompresso), raw_len (byte trasferiti), elapsed, error."""
        if polite:
            self._wait()
        self.requests += 1
        h = {"User-Agent": UA, "Accept": "*/*", "Accept-Encoding": "gzip, deflate"}
        if headers:
            h.update(headers)
        req = urllib.request.Request(url, headers=h, method=method)
        opener = self._follow if follow else self._nofollow
        t0 = time.time()
        res = {"ok": False, "url": url, "final_url": url, "status": 0, "headers": {}, "set_cookie": [],
               "body": b"", "raw_len": 0, "elapsed": 0.0, "error": None}
        resp = None
        for attempt in range(3):  # gli errori di connessione sono spesso passeggeri: ritenta con pausa crescente
            try:
                resp = opener.open(req, timeout=self.timeout)
                break
            except urllib.error.HTTPError as e:
                resp = e  # ha status, headers e body leggibili
                break
            except Exception as e:  # DNS, timeout, rete irraggiungibile, TLS...
                res["error"] = f"{type(e).__name__}: {e}"
                if attempt < 2 and not isinstance(e, ssl.SSLCertVerificationError):
                    time.sleep(2 * (attempt + 1))
                    continue
                res["elapsed"] = time.time() - t0
                return res
        res["error"] = None
        try:
            res["status"] = getattr(resp, "status", None) or resp.getcode()
            res["final_url"] = getattr(resp, "url", url) or url
            hdrs = resp.headers
            res["headers"] = {k.lower(): v for k, v in hdrs.items()}
            # header a lista ripetuti su più righe (es. due "Vary"): vanno uniti (RFC 9110 §5.3), non sovrascritti
            for lk in ("vary", "cache-control", "link"):
                vals = hdrs.get_all(lk) or []
                if len(vals) > 1:
                    res["headers"][lk] = ", ".join(vals)
            res["set_cookie"] = hdrs.get_all("Set-Cookie") or []
            if method != "HEAD":
                raw = resp.read(maxbytes + 1)
                res["raw_len"] = len(raw)
                enc = res["headers"].get("content-encoding", "").lower()
                try:
                    if enc == "gzip":
                        raw = gzip.decompress(raw)
                    elif enc == "deflate":
                        raw = zlib.decompress(raw)
                except Exception:
                    pass
                res["body"] = raw[:maxbytes]
            res["ok"] = True
        except Exception as e:
            res["error"] = f"{type(e).__name__}: {e}"
        res["elapsed"] = time.time() - t0
        return res

    @staticmethod
    def text(res):
        b = res.get("body") or b""
        ct = res.get("headers", {}).get("content-type", "")
        m = re.search(r"charset=([\w-]+)", ct, re.I)
        for enc in ([m.group(1)] if m else []) + ["utf-8", "latin-1"]:
            try:
                return b.decode(enc)
            except Exception:
                continue
        return b.decode("utf-8", "replace")


# --------------------------------------------------------------------------- TLS
def tls_info(host, port=443, timeout=15):
    """Certificato del server: giorni alla scadenza, emittente, versione TLS. Errore esplicito se fallisce."""
    ctx = CTX
    try:
        with socket.create_connection((host, port), timeout=timeout) as s:
            with ctx.wrap_socket(s, server_hostname=host) as ss:
                cert = ss.getpeercert()
                ver = ss.version()
        not_after = ssl.cert_time_to_seconds(cert["notAfter"])
        days = int((not_after - time.time()) / 86400)
        issuer = dict(x[0] for x in cert.get("issuer", ()))
        subj = dict(x[0] for x in cert.get("subject", ()))
        san = [v for k, v in cert.get("subjectAltName", ()) if k == "DNS"]
        return {"ok": True, "days_left": days, "issuer": issuer.get("organizationName") or issuer.get("commonName"),
                "cn": subj.get("commonName"), "san": san, "tls": ver, "not_after": cert["notAfter"]}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


# --------------------------------------------------------------------------- DNS over HTTPS
_TYPES = {"A": 1, "NS": 2, "CNAME": 5, "SOA": 6, "MX": 15, "TXT": 16, "AAAA": 28, "DS": 43, "CAA": 257}
_doh_cache = {}


def doh(name, rtype, timeout=20):
    """DNS-over-HTTPS (dns.google). Ritorna {ok, status, answers:[{type,data}]}.
    Solo sezione Answer. ok=False => query fallita: NON concludere che il record manca."""
    key = (name.lower(), rtype)
    if key in _doh_cache:
        return _doh_cache[key]
    url = f"https://dns.google/resolve?name={urllib.parse.quote(name)}&type={rtype}"
    out = {"ok": False, "status": None, "answers": [], "error": None}
    for attempt in range(2):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
                d = json.load(r)
            out["status"] = d.get("Status")
            out["answers"] = [{"type": a.get("type"), "data": a.get("data", "")} for a in d.get("Answer", [])]
            out["ok"] = d.get("Status") in (0, 3)  # 0 ok/NODATA, 3 NXDOMAIN: entrambi sono risposte vere
            out["error"] = None if out["ok"] else f"Status={d.get('Status')}"
            break
        except Exception as e:
            out["error"] = f"{type(e).__name__}: {e}"
            time.sleep(0.5)
    _doh_cache[key] = out
    return out


def doh_values(name, rtype):
    """Valori della risposta, includendo la catena CNAME se la query chiede altro tipo."""
    r = doh(name, rtype)
    want = _TYPES.get(rtype)
    vals = [a["data"] for a in r["answers"] if a["type"] == want]
    return r, vals


def txt_join(s):
    """Un record TXT puo' arrivare spezzato in stringhe tra virgolette."""
    parts = re.findall(r'"((?:[^"\\]|\\.)*)"', s)
    return "".join(parts) if parts else s.strip('"')


# --------------------------------------------------------------------------- HTML
class PageParser(HTMLParser):
    VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.lang = None
        self.metas, self.links, self.scripts, self.imgs, self.anchors = [], [], [], [], []
        self.iframes, self.forms, self.headings, self.jsonld = [], [], [], []
        self.landmarks = set()
        self.footer_text = []
        self.body_words = 0
        self._stack = []
        self._cur_script = None
        self._in_title = False
        self._cur_heading = None
        self._cur_form = None
        self._cur_anchor = None
        self._label_for = set()
        self._inline_budget = 400_000
        self.inline_scripts = []
        self.labels_for = set()
        self._label_depth = 0

    def handle_starttag(self, tag, attrs):
        a = {k: (v if v is not None else "") for k, v in attrs}
        if tag not in self.VOID:
            self._stack.append(tag)
        if tag == "html":
            self.lang = a.get("lang")
        elif tag == "title":
            self._in_title = True
        elif tag == "meta":
            self.metas.append(a)
        elif tag == "link":
            self.links.append(a)
        elif tag == "script":
            self._cur_script = {"attrs": a, "text": ""}
        elif tag == "img":
            self.imgs.append(a)
        elif tag == "iframe":
            self.iframes.append(a)
        elif tag == "a":
            self._cur_anchor = {"attrs": a, "text": ""}
        elif tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self._cur_heading = [int(tag[1]), ""]
        elif tag in ("main", "nav", "header", "footer", "aside"):
            self.landmarks.add(tag)
        elif tag == "form":
            self._cur_form = {"attrs": a, "inputs": []}
        elif tag in ("input", "select", "textarea") and self._cur_form is not None:
            if self._label_depth > 0:
                a = dict(a, _in_label="1")  # etichetta implicita: <label><input> ... </label>
            self._cur_form["inputs"].append((tag, a))
        elif tag == "label":
            self._label_depth += 1
            if a.get("for"):
                self.labels_for.add(a["for"])
        if a.get("role") in ("main", "navigation", "banner", "contentinfo", "complementary", "search"):
            self.landmarks.add("role:" + a["role"])

    def handle_endtag(self, tag):
        if tag == "label" and self._label_depth > 0:
            self._label_depth -= 1
        if tag == "title":
            self._in_title = False
        elif tag == "script" and self._cur_script is not None:
            s = self._cur_script
            self._cur_script = None
            if s["attrs"].get("type") == "application/ld+json":
                self.jsonld.append(s["text"])
            elif not s["attrs"].get("src") and self._inline_budget > 0:
                self.inline_scripts.append(s["text"][: self._inline_budget])
                self._inline_budget -= len(s["text"])
            self.scripts.append(s["attrs"])
        elif tag == "a" and self._cur_anchor is not None:
            self._cur_anchor["text"] = self._cur_anchor["text"].strip()
            self.anchors.append(self._cur_anchor)
            self._cur_anchor = None
        elif tag in ("h1", "h2", "h3", "h4", "h5", "h6") and self._cur_heading is not None:
            self._cur_heading[1] = self._cur_heading[1].strip()
            self.headings.append(tuple(self._cur_heading))
            self._cur_heading = None
        elif tag == "form" and self._cur_form is not None:
            self.forms.append(self._cur_form)
            self._cur_form = None
        if tag in self._stack:
            while self._stack:
                if self._stack.pop() == tag:
                    break

    def handle_data(self, data):
        if self._cur_script is not None:
            self._cur_script["text"] += data
            return
        if self._in_title:
            self.title += data
        if self._cur_heading is not None:
            self._cur_heading[1] += data
        if self._cur_anchor is not None:
            self._cur_anchor["text"] += data
        if "footer" in self._stack:
            self.footer_text.append(data)
        if "style" not in self._stack and "noscript" not in self._stack:
            self.body_words += len(data.split())

    # helpers
    def meta(self, key, attr="name"):
        for m in self.metas:
            if m.get(attr, "").lower() == key.lower():
                return m.get("content", "")
        return None

    def link_rel(self, rel):
        return [l for l in self.links if rel in l.get("rel", "").lower().split()]

    def footer(self):
        return re.sub(r"\s+", " ", " ".join(self.footer_text)).strip()


def parse_html(text):
    p = PageParser()
    try:
        p.feed(text)
        p.close()
    except Exception:
        pass
    p.title = re.sub(r"\s+", " ", p.title).strip()
    return p


def html_to_text(html):
    """Testo visibile approssimato (per leggere pagine legali)."""
    html = re.sub(r"(?is)<(script|style|noscript).*?</\1>", " ", html)
    html = re.sub(r"(?s)<[^>]+>", " ", html)
    import html as _h
    return re.sub(r"\s+", " ", _h.unescape(html)).strip()


# --------------------------------------------------------------------------- immagini
def image_size(data):
    """(larghezza, altezza, formato) letti dall'intestazione; None se non riconosciuta."""
    try:
        if data[:8] == b"\x89PNG\r\n\x1a\n":
            w, h = struct.unpack(">II", data[16:24])
            return w, h, "png"
        if data[:6] in (b"GIF87a", b"GIF89a"):
            w, h = struct.unpack("<HH", data[6:10])
            return w, h, "gif"
        if data[:2] == b"\xff\xd8":
            i = 2
            while i < len(data) - 9:
                if data[i] != 0xFF:
                    i += 1
                    continue
                m = data[i + 1]
                if m in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                    h, w = struct.unpack(">HH", data[i + 5:i + 9])
                    return w, h, "jpeg"
                seg = struct.unpack(">H", data[i + 2:i + 4])[0]
                i += 2 + seg
        if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
            kind = data[12:16]
            if kind == b"VP8X":
                w = 1 + int.from_bytes(data[24:27], "little")
                h = 1 + int.from_bytes(data[27:30], "little")
                return w, h, "webp"
            if kind == b"VP8 ":
                w, h = struct.unpack("<HH", data[26:30])
                return w & 0x3FFF, h & 0x3FFF, "webp"
            if kind == b"VP8L":
                b = data[21:25]
                bits = int.from_bytes(b, "little")
                return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1, "webp"
    except Exception:
        return None
    return None


# --------------------------------------------------------------------------- varie
def host_of(url):
    return urllib.parse.urlsplit(url).hostname or ""


def same_site(host, base):
    host, base = host.lower(), base.lower()
    return host == base or host.endswith("." + base) or base.endswith("." + host)


def piva_valid(num):
    """Partita IVA italiana: 11 cifre + cifra di controllo (Luhn modificato)."""
    if not re.fullmatch(r"\d{11}", num or ""):
        return False
    s = 0
    for i, ch in enumerate(num[:10]):
        d = int(ch)
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        s += d
    return (10 - s % 10) % 10 == int(num[10])
