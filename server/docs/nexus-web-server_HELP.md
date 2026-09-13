```
╔══════════════════════════════════════════════════════════════════════════════════╗
║                                                                                  ║
║        N e X u S   W E B   S E R V E R   —   H E L P   &   M A N U A L          ║
║                                                                                  ║
║        Portable HTTPS host + Universal AI API proxy                              ║
║        One file · Pure Python · No pip · No npm · No node                        ║
║        Sane · Simple · Secure · Sustainable                                      ║
║                                                                                  ║
╚══════════════════════════════════════════════════════════════════════════════════╝
```

> One `python3` file serves any web app folder over HTTPS **and** fronts every AI provider
> behind a shared `/api/*` proxy that injects API keys **server-side** from a local secrets
> file — so no browser ever holds a secret key. New providers are declared in the env file,
> no code edits needed. That is what makes it a *universal API server*.

---

## START HERE — NeXuS Node

On a NeXuS node the proxy is managed through the `api-proxy` alias.  
Script: `~/scripts/nexus-api-proxy.sh`

```bash
api-proxy start     # launch in tmux session 'nexus-proxy' + charcard editor on :7420
api-proxy status    # running? which providers have live keys?
api-proxy logs      # attach to the session to watch live output  (Ctrl-B D to detach)
api-proxy stop
api-proxy restart
```

After start, open `https://localhost:8443` in a browser and accept the self-signed cert once.

```bash
# Quick verify — should return ok:true plus a provider key map
curl -sk https://localhost:8443/api/health | python3 -m json.tool
```

The manual `python3 nexus_web_server.py --root … --cert … --key …` form documented below
is for standalone or non-node deployments only. On a NeXuS node, always use `api-proxy`.

---

## 0 ·  WHERE IS EVERYTHING

```
PROJECT DIRECTORY
  ~/Projects/nexus-web-server/
  ├── nexus_web_server.py            the entire server (~550 lines, stdlib only)
  ├── README.md                      short overview
  ├── .local.env.example             copy → .local.env, add your keys
  └── docs/
      ├── nexus-web-server_HELP.md   THIS FILE
      └── action_report.md           per-task change log

VERSION CONTROL (Fossil)
  Repository:  ~/museum/nexus-web-server.fossil
  Open:        cd ~/Projects/nexus-web-server && fossil open ~/museum/nexus-web-server.fossil --keep

GLOBAL SECRETS  (shared by every NeXuS app)
  ~/NeXuS/secrets/nexus.env          chmod 600
  ~/NeXuS/secrets/nexus.env.example  template, no secrets

EXAMPLE CONSUMING APP  (web character generator)
  ~/Projects/adv-ai-nexus/advanced-ai-character-generator-terminal-access/
  ├── dist/                  built app — passed as --root to this server
  ├── cert.pem / key.pem     TLS material
  ├── launch.sh              interactive launcher (calls this server for production)
  └── services/nexusProxy.ts browser fetch interceptor → same-origin /api/*
```

---

## 1 ·  REQUIREMENTS CHECKLIST

**REQUIRED** = server will not start without it.  
**CONDITIONAL** = only needed for that specific feature.  
**OPTIONAL** = convenience only.

```
┌────┬───────────────────────────────┬───────────┬───────────────────────────────────────────────┐
│ #  │ Requirement                   │ Level     │ Why / How to satisfy                           │
├────┼───────────────────────────────┼───────────┼───────────────────────────────────────────────┤
│ 1  │ Python 3.8 or newer           │ REQUIRED  │ Uses walrus (:=). Check: python3 --version     │
│ 2  │ Python standard library only  │ REQUIRED  │ ssl / http.server / urllib / json — bundled    │
│    │                               │           │ with Python. No pip, no venv.                  │
│ 3  │ TLS cert.pem + key.pem        │ REQUIRED  │ HTTPS. Self-signed is fine — see §4.           │
│    │                               │           │ Pass --cert/--key or place next to the script. │
│ 4  │ A web ROOT directory          │ REQUIRED  │ --root <dir> (default ./dist)                  │
│ 5  │ An open TCP port (default 8443│ REQUIRED  │ --port <n>. Ports <1024 require root/sudo.     │
├────┼───────────────────────────────┼───────────┼───────────────────────────────────────────────┤
│ 6  │ ~/NeXuS/secrets/nexus.env     │CONDITIONAL│ Needed for key-required providers              │
│    │ (or a project .local.env)     │           │ (pollinations / openai / mistral / groq / or)  │
│    │                               │           │ Keyless providers work without this.           │
│ 7  │ chmod 600 on any env file     │CONDITIONAL│ Secrets must be owner-only. Server warns if not│
│ 8  │ OpenSSL                       │CONDITIONAL│ Only to generate a self-signed cert (§4).      │
│    │                               │           │ Not needed at runtime.                         │
│ 9  │ Node.js 18+ / npm             │CONDITIONAL│ Only to (re)build a JS app's dist/.            │
│    │                               │           │ Not needed to run this server.                 │
│ 10 │ Network egress to providers   │CONDITIONAL│ For cloud providers. Local Ollama/aichat        │
│    │ (or local Ollama/aichat)      │           │ work with no WAN access.                       │
├────┼───────────────────────────────┼───────────┼───────────────────────────────────────────────┤
│ 11 │ Fossil 2.x                    │ OPTIONAL  │ Version control only. Not needed to run.       │
│ 12 │ Browser that accepts a        │ OPTIONAL  │ Self-signed cert → add a one-time exception.   │
│    │ self-signed cert              │           │                                                │
└────┴───────────────────────────────┴───────────┴───────────────────────────────────────────────┘
```

**Boot minimum (static serve only):**  items 1 2 3 4 5  
**Add AI with a paid provider:**  items 6 7  
**Add AI with keyless providers (AI Horde, Ollama):**  boot minimum only — no keys required

---

## 2 ·  WHAT IT DOES  (two jobs, cleanly split)

```
                    ┌──────────────────────────────────────────────────┐
  Browser / app ───▶│           NeXuS Web Server  (HTTPS :8443)         │
                    │                                                  │
                    │   ┌─────────────────┐   ┌──────────────────────┐ │
  GET /index.html ─▶│   │  A) STATIC       │   │  B) PROXY /api/*      │─▶ gen.pollinations.ai
  GET /assets/…   ─▶│   │  serve --root    │   │  inject key from     │─▶ api.mistral.ai
  POST /api/llm/… ─▶│   │  SPA fallback    │   │  nexus.env / .local  │─▶ localhost:11434
  GET  /api/…     ─▶│   │  landing index   │   │  never leaks sk_     │─▶ …any provider
                    │   └─────────────────┘   └──────────────────────┘ │
                    └──────────────────────────────────────────────────┘
       FILES are swappable.       The PROXY is the shared engine. Keys stay here.
```

---

## 3 ·  MANUAL QUICK START  (standalone / non-node)

```bash
# One-time: put your key in the global env (or use a project .local.env — see §6)
mkdir -p ~/NeXuS/secrets
printf 'POLLINATIONS_API_KEY=sk_xxx\n' > ~/NeXuS/secrets/nexus.env
chmod 600 ~/NeXuS/secrets/nexus.env

# Run pointed at an app's built folder
python3 ~/Projects/nexus-web-server/nexus_web_server.py \
    --root  ~/Projects/adv-ai-nexus/advanced-ai-character-generator-terminal-access/dist \
    --cert  ~/Projects/adv-ai-nexus/advanced-ai-character-generator-terminal-access/cert.pem \
    --key   ~/Projects/adv-ai-nexus/advanced-ai-character-generator-terminal-access/key.pem \
    --port  8443

# Open — accept the self-signed cert once
#   https://localhost:8443
```

**Multi-app mode** — point `--root` at a directory containing several app folders.  
Each serves at `/<folder>/` and `/` shows a landing list.

```bash
python3 nexus_web_server.py --root ~/nexus-web --port 8443   # → /chargen/  /oc/  …
```

---

## 4 ·  GENERATE A SELF-SIGNED CERT

```bash
openssl req -x509 -newkey rsa:2048 -nodes -keyout key.pem -out cert.pem \
    -days 825 -subj "/CN=localhost" \
    -addext "subjectAltName=DNS:localhost,IP:127.0.0.1"
chmod 600 key.pem
```

Place `cert.pem` and `key.pem` next to the script, or pass `--cert` / `--key` explicitly.

---

## 5 ·  COMMAND-LINE FLAGS

```
python3 nexus_web_server.py [OPTIONS]

  --root DIR     Web root to serve                     (default: ./dist)
  --port N       TCP port                              (default: 8443)
  --host ADDR    Bind address                          (default: 0.0.0.0 — all interfaces)
  --cert FILE    TLS certificate PEM                   (default: ./cert.pem)
  --key  FILE    TLS private-key PEM                   (default: ./key.pem)
  --env  FILE    Explicit .local.env path              (otherwise auto-discovered — §6)
```

---

## 6 ·  SECRETS & PROVIDERS

### 6.1  Key lookup precedence  (highest wins)

```
  1.  process environment        POLLINATIONS_API_KEY=… python3 nexus_web_server.py
  2.  .local.env  (project)      auto-found in CWD, script dir, or web-root parent
  3.  ~/NeXuS/secrets/nexus.env  global, shared by all NeXuS apps
  4.  ~/NeXuS/secrets/pollinations.key  (legacy, POLLINATIONS_API_KEY only)
```

`.local.env` overrides the global `nexus.env` for a single project:

```bash
cp ~/Projects/nexus-web-server/.local.env.example  ./.local.env
chmod 600 ./.local.env
```

### 6.2  Built-in providers

```
  KEY-REQUIRED:   pollinations · openai · mistral · groq · openrouter
  KEYLESS:        aihorde · ollama (localhost:11434) · aichat (localhost:3030)
```

Key variable names:
`POLLINATIONS_API_KEY`  `OPENAI_API_KEY`  `MISTRAL_API_KEY`  `GROQ_API_KEY`  `OPENROUTER_API_KEY`

### 6.3  Add a new provider — no code edit

Declare any OpenAI-compatible provider in the env file:

```ini
PROVIDER_<ID>_BASE_URL=https://host/v1     # REQUIRED — defines the provider
PROVIDER_<ID>_API_KEY=sk-...               # optional — absent means keyless
PROVIDER_<ID>_KIND=chat|image|chat+image   # optional (default: chat)
PROVIDER_<ID>_LABEL=Friendly Name          # optional
```

Example — a local vLLM or LM-Studio instance:

```ini
PROVIDER_MYLLM_BASE_URL=http://localhost:8000/v1
PROVIDER_MYLLM_API_KEY=sk-local
PROVIDER_MYLLM_LABEL=My Local LLM
```

It appears instantly in `/api/providers` and is callable at  
`POST /api/llm/myllm/v1/chat/completions` — no restart required.

### 6.4  Three security guarantees (automatic)

```
  NEVER SERVED       Static handler returns 404 for any .env / .key / .pem / dotfile,
                     even if the file sits inside the web root.

  NEVER COMMITTED    On startup, when a .local.env is found, the server appends secret
                     patterns to .gitignore in that folder (append-only, idempotent).

  NEVER LEAKED       Keys are injected into upstream calls only. /api/providers reports
                     key_present: true/false. Keys are never logged or returned.
```

---

## 7 ·  HTTP ROUTES

```
┌────────┬──────────────────────────────────────────────────┬─────────────────────────────────┐
│ METHOD │ ROUTE                                             │ PURPOSE                         │
├────────┼──────────────────────────────────────────────────┼─────────────────────────────────┤
│ GET    │ /api/health                                       │ liveness + provider key status  │
│ GET    │ /api/providers                                    │ sanitized registry (no secrets) │
│ GET    │ /api/models/image  ·  /api/models/text            │ live Pollinations model lists   │
│ GET    │ /api/models/provider/{id}                          │ live /models for any provider   │
│ GET    │ /api/pollinations/image?prompt=&model=&w=&h=       │ image proxy — key injected      │
│ POST   │ /api/llm                                           │ chat proxy — {provider, …openai}│
│ POST   │ /api/llm/{provider}/v1/chat/completions            │ vanilla OpenAI body             │
│ GET    │ *                                                 │ static file (SPA fallback)      │
└────────┴──────────────────────────────────────────────────┴─────────────────────────────────┘
```

---

## 8 ·  HOW APPS USE IT

### 8.1  The web char-gen (automatic via nexusProxy.ts)

`services/nexusProxy.ts` installs a `fetch` interceptor at startup that rewrites calls to
`gen.pollinations.ai`, `api.mistral.ai`, `api.groq.com`, etc. → same-origin `/api/llm/<provider>/…`
and strips the `Authorization` header. Transparent to the app — same method, same body, same streaming.

### 8.2  OpenCharacters or any custom-endpoint client

Add one custom model pointing at this proxy:

```json5
{
  name: "gpt-5.4",
  endpointUrl: "https://localhost:8443/api/llm/pollinations/v1/chat/completions",
  apiKey: "unused",
  maxSequenceLength: 8192,
  type: "chat-completion"
}
```

The browser sends no key. The server injects it.

---

## 9 ·  REQUEST FLOW

```
  ┌──────────┐   POST gen.pollinations.ai/v1/chat/completions   ┌─────────────────┐
  │ BROWSER  │──────────────────────────────────────────────▶  │ fetch           │
  │  (app)   │                                                   │ interceptor     │
  └──────────┘                                                   └───────┬─────────┘
       ▲                                                                 │ rewrite + strip key
       │ streamed reply                                                  ▼
       │                       ┌──────────────────────────────────────────────────┐
       │                       │ NeXuS Web Server  POST /api/llm/pollinations/…   │
       │                       │   looks up base_url + key from nexus.env         │
       │                       │   adds:  Authorization: Bearer sk_***            │
       │                       └──────────────────────┬───────────────────────────┘
       │                                              ▼
       │                              gen.pollinations.ai  (real upstream)
       └──────────────────────────────────────────────┘
                    sk_ key exists only on the server.
```

---

## 10 ·  SELF-TEST

```bash
B=https://localhost:8443

# Liveness + key status
curl -sk $B/api/health | python3 -m json.tool

# Provider registry (no secrets — booleans only)
curl -sk $B/api/providers | python3 -m json.tool | head -40

# Image proxy — should produce a JPEG
curl -sk "$B/api/pollinations/image?prompt=fox&width=256&height=256" -o test.jpg && file test.jpg

# Chat proxy — should return assistant text
curl -sk -X POST $B/api/llm/pollinations/v1/chat/completions \
     -H 'Content-Type: application/json' \
     -d '{"model":"openai","messages":[{"role":"user","content":"say ok"}]}'

# Security check — this MUST return 404
curl -sk $B/.local.env -w ' <HTTP %{http_code}>\n'
```

---

## 11 ·  TROUBLESHOOTING

```
SYMPTOM                                   CAUSE / FIX
────────────────────────────────────────  ────────────────────────────────────────────────────
TLS cert/key not found                    Pass --cert/--key, or generate them (§4)
Web root not found                        --root path does not exist; check it
Browser: connection not private           Self-signed cert — add a one-time exception (expected)
502  needs a key: set X in nexus.env      Key-required provider with no key loaded (§6)
502  read operation timed out             Upstream cold-start latency — retry
Provider missing from /api/providers      PROVIDER_<ID>_BASE_URL not set or typo (§6.3)
Port 8443 in use                          Another instance running — stop it or use --port
Image works, chat does not                Chat provider needs a key or a reachable local server
.local.env is 0o644 warning               Run:  chmod 600 .local.env
```

---

## 12 ·  DEPENDENCY SUMMARY

```
RUNTIME  (server)     python3 >= 3.8              REQUIRED
                      python3 stdlib              REQUIRED — bundled with Python
                      cert.pem + key.pem          REQUIRED
                      --root directory            REQUIRED
                      nexus.env / .local.env      REQUIRED for key-required providers
BUILD    (JS apps)    node >= 18 + npm            CONDITIONAL — only to rebuild dist/
TOOLING               openssl                     OPTIONAL — only to generate certs
                      fossil 2.x                  OPTIONAL — version control only
PIP PACKAGES          none                        zero pip installs, no venv needed
```

The whole point: to run the server you need Python and nothing else.  
Node and npm are only for rebuilding a JavaScript front-end — never for serving or proxying.

---

*NeXuS Web Server — Sane · Simple · Secure · Sustainable.  Keys stay home.*
