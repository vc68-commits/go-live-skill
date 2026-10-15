# go-live-skill

Skills for [Claude Code](https://claude.com/claude-code) that check whether a website or web app is ready to launch and produce a prioritized checklist. This repo contains two versions:

| Skill | Version | How it works | Dependencies |
|---|---|---|---|
| [`go-live`](./SKILL.md) | 1.4.0 | The model runs `curl`/`dig`/`grep` and fills in the checklist | `dig`, `curl`, `python3` |
| [`go-live-v2`](./go-live-v2/SKILL.md) | 2.0.0 | A Python script collects the facts (read-only), the model interprets them | Python 3.11+; optional: Playwright, Node.js |

Each check is reported as ✅ / ⚠️ / ❌ / 🔲 (manual), with priority **P0** (blocks launch) → P1 → P2 → P3.

v2 does not replace v1: it reuses v1's category definitions (A–R), priority rules and operating notes. **Install both.**

> Note: the skill files themselves (`SKILL.md`) and their reports are written in Italian.

---

## Installation

### Requirements

- Claude Code, installed and working
- `git`
- For v1: `curl`, `dig`, `python3`
- For v2: `python3` ≥ 3.11 (standard library only; `tomllib` is required)
- For the optional v2 browser module: Node.js (recent LTS) with `npm`, plus Playwright and Chromium (see below)

### 1. go-live (v1)

Claude Code skills live in `~/.claude/skills/`. Clone the repo into a working folder and link the skills:

```bash
git clone git@github.com:vc68-commits/go-live-skill.git ~/projects/go-live-skill
mkdir -p ~/.claude/skills
ln -s ~/projects/go-live-skill ~/.claude/skills/go-live
```

v1 is the root of the repo (`SKILL.md`). The symlink also exposes the `go-live-v2/` folder inside `go-live/`. This is harmless, but if you prefer to avoid it, copy only the v1 files:

```bash
mkdir -p ~/.claude/skills/go-live
cp ~/projects/go-live-skill/{SKILL.md,README.md,LICENSE.txt} ~/.claude/skills/go-live/
```

### 2. go-live-v2

```bash
ln -s ~/projects/go-live-skill/go-live-v2 ~/.claude/skills/go-live-v2
```

or, without a symlink:

```bash
cp -R ~/projects/go-live-skill/go-live-v2 ~/.claude/skills/go-live-v2
```

After this step v2 is already usable: the collector (`scripts/collect.py`) only needs the Python standard library.

### 3. v2 browser module (optional)

This module covers the checks that need a real browser: cookie banner and cookies before/after consent, CSP/JS errors, LCP/CLS/TBT, accessibility with axe-core, keyboard navigation, mobile layout and Lighthouse. Enable it with `--browser` or with `[browser] enabled = true` in the config file.

The script looks for its dependencies **inside the skill folder**, so create the environments there:

```bash
cd ~/.claude/skills/go-live-v2

# Python: Playwright (pinned version) and Chromium
python3 -m venv .venv
.venv/bin/pip install "playwright==1.63.0"
.venv/bin/playwright install chromium

# Node: axe-core and Lighthouse (from package.json)
npm install
```

If you use a symlink, `.venv/` and `node_modules/` end up inside the cloned repo. **Do not commit them**: `go-live-v2/` has no `.gitignore`.

Without the browser module, the checks that need it appear as 🔲 (not run), never as passed.

### 4. Verify

```bash
python3 ~/.claude/skills/go-live-v2/scripts/collect.py --help
```

Then open a Claude Code session and type `/go-live` or `/go-live-v2`: both skills should be listed as available.

---

## Usage

### go-live (v1)

```
/go-live
/go-live https://example.com
```

Reads the project context (`CLAUDE.md`, `package.json`, config files), detects the framework, scans the codebase, runs HTTP checks against the live domain and saves `GO-LIVE-CHECKLIST.md` in the project root.

### go-live-v2

```
/go-live-v2
/go-live-v2 https://example.com
```

Or straight from the terminal, without going through the model:

```bash
python3 ~/.claude/skills/go-live-v2/scripts/collect.py --config go-live.toml --md            # about 1 minute
python3 ~/.claude/skills/go-live-v2/scripts/collect.py --config go-live.toml --browser --md  # about 2.5 minutes
python3 ~/.claude/skills/go-live-v2/scripts/collect.py --url https://example.com --md        # no config file
```

Main options: `--config`, `--url`, `--browser`, `--md`, `--no-history`, `--notify`, `--isagentic`, `--ax`. The last three send the domain to external services (see the comments in the template).

Each run writes `~/go-live-test/<domain>/<date>.json` and `.md`, and compares the result with the previous run (worse / better / new). The collector only makes read requests, at 1 request per second, and never modifies the site, the server or the DNS.

### Per-site configuration

Copy the template next to your project and fill it in:

```bash
cp ~/.claude/skills/go-live-v2/templates/go-live.toml ./go-live.toml
```

The essential fields are `domain` and `url`. The more precise the configuration (`[email].providers`, `auth_via_email`, `[legal].expected_subprocessors`, `[ignore].checks`), the more reliable the checks. The token for Telegram alerts never goes in the `.toml` file: it lives in `~/.config/go-live/telegram.env`.

---

## Categories

v1 defines 18 categories (A–R); v2 adds two:

- **S** — cross-source consistency (sub-processors listed in the privacy policy vs. detected vendors, declared email providers vs. DNS, VAT number, cookies vs. cookie policy)
- **Z** — internal script errors (a section that crashes is never reported as passed)

The first nine, from the bollette.it experience:

| # | Category | Automatic checks | Manual checks |
|---|---|---|---|
| A | Infrastructure & DNS | SSL/HTTPS, redirects | DNS, MX, DKIM/SPF |
| B | Security | HSTS, CSP, X-Frame, nosniff | Rate limiting, pentest |
| C | SEO Foundation | robots.txt, sitemap, canonical, schema, GA4, GSC meta | GSC verified, GA4↔GSC link |
| D | GEO / AI | llms.txt, AI-friendly markup | AI crawler test |
| E | Legal & GDPR | Privacy/Terms/Cookie pages, banner, consent mode | DPO, DPIA, retention policy |
| F | Company info | VAT number, address and legal links in the footer | — |
| G | Performance | Bundle size, optimized images | Lighthouse, CWV |
| H | Content & UX | 404, OG tags, favicon, error pages | Landing keywords, competitor gap |
| I | Monitoring | Sentry/error tracking, uptime | Alerts, log review |

The full list, with each individual check, is in [`SKILL.md`](./SKILL.md).

---

## Updating

```bash
cd ~/projects/go-live-skill && git pull
```

If you copied the files instead of using symlinks, repeat the copy after the `pull`. The v2 `.venv/` and `node_modules/` are left untouched; re-run `npm install` only if `package.json` changes.

## License

See [`LICENSE.txt`](./LICENSE.txt).
