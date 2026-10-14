# nexus-bifrost-bridge

> **The Rainbow Bridge.** Universal HTTPS proxy and web interface layer connecting every NeXuS realm into one sovereign gateway.

**Author:** hackenstacks@protonmail.com  
**Status:** ✅ Production — fully operational  
**Principles:** Sane · Simple · Secure · Stealthy · Beautiful  

---

## What It Is

Bifrost is a single Python file (`nexus_web_server.py`) that does three things:

1. **Serves static web apps** — drop a folder in `web/` and it's instantly available at `https://localhost:8443/<foldername>/`
2. **Proxies AI provider API calls** — injects API keys server-side; the browser never sees a key
3. **Routes to backend services** — forwards `/search/`, `/nncc/`, `/wiki/` etc. to local processes on their own ports

One process. One port. One self-signed cert. Everything NeXuS runs through it.

```
Browser → https://localhost:8443
              │
              ├── /                    NeXuS hub (web/index.html)
              ├── /oc/                 OpenCharacters (web/oc/)
              ├── /chargen/            AI Character Generator
              ├── /nncc/               Network Command Center (FastAPI :8801)
              ├── /search/             NXS Search (:5000)
              ├── /wiki/               Wiki (:6789)
              ├── /docs/               MkDocs (:8000)
              ├── /aichat/             aichat (:3030)
              ├── /api/llm/*           AI proxy — keys injected server-side
              ├── /api/nexus/tasks     Taskwarrior REST API
              ├── /api/nexus/governor  Resource governor
              ├── /api/nexus/ncm/*     Network manager
              └── /api/health          Liveness + provider key status
```

---

## Quick Start

### Prerequisites

- Python 3.11+
- `openssl` (for self-signed cert — auto-generated on first run)
- API keys in `~/NeXuS/secrets/nexus.env` (optional — keyless providers work without any)

### 1. Clone

```bash
git clone https://github.com/hackenstacks/nexus-bifrost-bridge.git
cd nexus-bifrost-bridge
```

### 2. Set up secrets (optional)

```bash
mkdir -p ~/NeXuS/secrets
cat >> ~/NeXuS/secrets/nexus.env << 'EOF'
MISTRAL_API_KEY=your_key_here
GROQ_API_KEY=your_key_here
OPENROUTER_API_KEY=your_key_here
DEEPSEEK_API_KEY=your_key_here
EOF
chmod 600 ~/NeXuS/secrets/nexus.env
```

### 3. Start

```bash
python3 server/nexus_web_server.py --root web --port 8443
```

First run auto-generates `server/cert.pem` and `server/key.pem`.

### 4. Trust the certificate (one time)

Firefox / LibreWolf:
1. Open `https://localhost:8443`
2. Click **Advanced** → **Accept the Risk and Continue**

Or import `server/cert.pem` into your browser's certificate store for permanent trust.

### 5. Open

```
https://localhost:8443
```

---

## OpenRC Service (Alpine Linux)

```bash
# Install
doas cp bifrost.initd /etc/init.d/bifrost
doas chmod +x /etc/init.d/bifrost

# Enable at boot
doas rc-update add bifrost default

# Control
doas rc-service bifrost start
doas rc-service bifrost stop
doas rc-service bifrost restart
doas rc-service bifrost status
```

**Environment variables** (edit `/etc/init.d/bifrost` to override):

| Variable | Default | Description |
|---|---|---|
| `NEXUS_HOME` | `/home/user/NeXuS` | NeXuS root directory |
| `BIFROST_DIR` | `$NEXUS_HOME/bifrost-bridge` | Bifrost repo directory |
| `BIFROST_PORT` | `8443` | HTTPS port |
| `BIFROST_ROOT` | `$BIFROST_DIR/web` | Web root directory |
| `BIFROST_LOG` | `/var/log/bifrost.log` | Log file |
| `BIFROST_USER` | `user` | Run as this user |

---

## AI Provider Proxy

### How it works

All AI API calls go through `/api/llm/<provider>/v1/chat/completions`. Bifrost:
1. Reads the API key from `~/NeXuS/secrets/nexus.env` server-side
2. Injects it into the `Authorization` header
3. Forwards to the provider's real endpoint
4. Streams the SSE response back via HTTP/1.1 chunked transfer

The browser **never sees or sends a key**.

### Supported providers

| Provider | Key env var | Keyless? | Notes |
|---|---|---|---|
| `pollinations` | — | ✅ Free | Default for OC and chargen |
| `mistral` | `MISTRAL_API_KEY` | ❌ | |
| `groq` | `GROQ_API_KEY` | ❌ | |
| `openrouter` | `OPENROUTER_API_KEY` | ❌ | 200+ models |
| `deepseek` | `DEEPSEEK_API_KEY` | ❌ | |
| `google` | `GOOGLE_API_KEY` | ❌ | Gemini |
| `grok` | `GROK_API_KEY` | ❌ | xAI |
| `together` | `TOGETHER_API_KEY` | ❌ | |
| `hyperbolic` | `HYPERBOLIC_API_KEY` | ❌ | |
| `cerebras` | `CEREBRAS_API_KEY` | ❌ | |
| `ollama` | — | ✅ Local | Requires Ollama on :11434 |
| `aihorde` | — | ✅ Free | Distributed AI Horde |
| `nexus-router` | — | ✅ Local | NeXuS AI Router on :8810 |

### Example calls

```bash
# Streaming chat (Pollinations — no key needed)
curl -sk -X POST https://localhost:8443/api/llm/pollinations/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"openai","messages":[{"role":"user","content":"hello"}],"stream":true}'

# Non-streaming
curl -sk -X POST https://localhost:8443/api/llm/mistral/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"mistral-large-latest","messages":[{"role":"user","content":"hello"}]}'

# Health check — see which providers have keys
curl -sk https://localhost:8443/api/health | python3 -m json.tool
```

### Adding a dynamic provider (no restart needed)

```bash
# Add to ~/NeXuS/secrets/nexus.env:
NEXUS_APP_myprovider_label=MyProvider
NEXUS_APP_myprovider_base_url=https://api.myprovider.com/v1
NEXUS_APP_myprovider_key_env=MYPROVIDER_API_KEY
MYPROVIDER_API_KEY=sk-...
```

---

## OpenCharacters (OC) Integration

OpenCharacters at `https://localhost:8443/oc/index.html` works fully through Bifrost with no API key required in the OC UI.

### How OC is wired

When Bifrost serves any HTML file from `/oc/`, it injects a script into `<head>` at serve time that:

1. **Intercepts `window.fetch()`** — rewrites all AI provider URLs to the local Bifrost proxy and strips the `Authorization` header (keys are injected server-side)
2. **Seeds IndexedDB** — writes `nexus-proxy` as the API key so OC's client-side key gate passes, and configures Pollinations as the default endpoint

```
OC → fetch('https://api.openai.com/v1/chat/completions')
       ↓  [injected fetch interceptor: rewrite + strip auth]
     fetch('https://localhost:8443/api/llm/pollinations/v1/chat/completions')
       ↓  [Bifrost: filter choices:[] preamble, HTTP/1.1 chunked SSE]
     OC handleStreamingResponse → streaming reply ✅
```

### OC-Fix Log — 8 bugs fixed (2026-10-14)

These are documented so future maintainers understand why the code is structured the way it is.

---

#### OC-Fix-01 — Inject not applied to registry-served HTML

**Error:** OC loaded but API calls hit OpenAI directly, no proxying.

**Cause:** Two code paths serve HTML. `_serve_static()` (direct `/oc/*` URLs) had `_OC_INJECT` applied. `_registry_static()` (when `/oc` is registered in the app registry as `static+static`) did not.

**Fix:** Added inject block to `_registry_static()`:
```python
if app["prefix"] in ("/oc", "/oc/") and ctype == "text/html":
    if "NeXuS proxy auto-config" not in html_str:
        data = html_str.replace("<head>", "<head>\n" + self._OC_INJECT, 1).encode("utf-8")
```

---

#### OC-Fix-02 — Double `/v1/v1/` in URL (stale IndexedDB)

**Error:** `unknown API route /api/llm/pollinations/v1/v1/chat/completions`

**Cause:** Seeded `endpointUrl` had `/v1` baked in. OC appends `/v1/chat/completions` to `endpointUrl`, producing a double `/v1`. The `seedDB` guard (`if result exists, return`) also prevented overwriting stale values from old sessions.

**Fix (3 layers):**
1. `endpointUrl` seeds end at provider base: `BASE+"/api/llm/pollinations"` (no `/v1`)
2. `seedDB` always overwrites `customModelConfigs` — no guard
3. Runtime fixer in fetch interceptor: `url.replace(/\/v1\/v1\//, '/v1/')`

---

#### OC-Fix-03 — `api.openai.com` routed to openai (no key)

**Error:** `handleStreamingResponse` crash — OC received error JSON instead of SSE stream.

**Cause:** OC hardcodes `https://api.openai.com/v1/chat/completions` for all streaming calls regardless of the UI model selection. The interceptor was mapping `api.openai.com` → `/api/llm/openai` which has no key. Bifrost returned an error JSON. OC tried to parse it as SSE and crashed.

**Fix:** Changed MAP:
```javascript
"api.openai.com": BASE+"/api/llm/pollinations"  // keyless, always available
```

---

#### OC-Fix-04 — `/v1` in MAP values causing double-v1

**Error:** Same `/v1/v1/` error but from the interceptor path.

**Cause:** MAP had `/v1` baked in (`BASE+"/api/llm/groq/v1"`). OC's URL already contains `/v1/chat/completions`. Concatenating them → double `/v1`.

**Fix:** Removed `/v1` from all MAP values. Bifrost's `LLM_PATH_RE` uses `(?:v1/)?` making it optional.

---

#### OC-Fix-05 — HTTP/1.0 broke `response.body.getReader()`

**Error:** `handleStreamingResponse` crash — `response.body` was null.

**Cause:** Bifrost defaulted to HTTP/1.0 (`BaseHTTPRequestHandler` default). The Fetch API's `response.body.pipeThrough(new TextDecoderStream()).getReader()` requires HTTP/1.1 to expose a `ReadableStream`. HTTP/1.0 responses do not expose `response.body` in modern browsers.

**Fix:**
```python
class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
```

---

#### OC-Fix-06 — HTTP/1.1 keep-alive hung all static responses

**Error:** All Bifrost links stopped working. Browser hung indefinitely after first request.

**Cause:** HTTP/1.1 persistent connections require responses to have `Content-Length` or `Transfer-Encoding: chunked`. Without either, the browser waits forever for the response to end.

**Fix:** `_send()` now forces connection close for all non-streaming responses:
```python
if "Connection" not in extra and "Transfer-Encoding" not in extra:
    self.close_connection = True
```
Streaming LLM responses explicitly set both headers and are exempt.

---

#### OC-Fix-07 — Raw 301 redirect missing `Content-Length: 0`

**Error:** Navigating to `https://localhost:8443/oc` showed "Blocked" in Firefox (0 bytes transferred).

**Cause:** The 301 redirect from `/oc` → `/oc/` in `_dispatch_registry()` used raw `send_response(301)` bypassing `_send()`. No `Content-Length` header, no `close_connection`. Browser waited for a body that never arrived.

**Fix:**
```python
self.close_connection = True
self.send_header("Content-Length", "0")
```

---

#### OC-Fix-08 — Pollinations `choices:[]` preamble chunk crashed OC

**Error:** `TypeError: Cannot read properties of undefined (reading 'text')` inside `handleStreamingResponse`.

**Cause:** Pollinations always sends a first SSE event as a content-filter preamble:
```
data: {"choices":[],"prompt_filter_results":[...]}
```
OC does `json.choices[0].text` without checking if `choices[0]` exists. Since `choices` is an empty array, this throws `TypeError`. No try-catch around this line — the entire reply dies.

**Fix:** Bifrost's streaming proxy filters SSE lines before forwarding:
```python
if isinstance(d.get("choices"), list) and len(d["choices"]) == 0:
    continue  # drop Pollinations filter-results preamble
```

---

## Taskwarrior REST API

```bash
GET  /api/nexus/tasks                        # all pending tasks
GET  /api/nexus/tasks?project=nexus.vault    # filter by project
GET  /api/nexus/tasks?status=completed       # filter by status
GET  /api/nexus/tasks/projects               # list projects + counts

POST /api/nexus/tasks
     {"description":"do the thing","project":"nexus.vault","priority":"H","due":"2026-10-20"}

POST /api/nexus/tasks/done    {"id": 4}
POST /api/nexus/tasks/delete  {"id": 4}
```

---

## Adding a Web App

```bash
# Static app
cp -r my-app/dist/ ~/NeXuS/bifrost-bridge/web/my-app/
# → https://localhost:8443/my-app/

# App with backend
# Add to ~/NeXuS/secrets/nexus.env:
NEXUS_APP_myapp_label=My App
NEXUS_APP_myapp_static=/path/to/dist
NEXUS_APP_myapp_backend=http://127.0.0.1:9000
NEXUS_APP_myapp_api_prefix=/api
```

---

## Security Model

- **No keys in browser** — all provider API keys are injected server-side only
- **Loopback-only sensitive endpoints** — `/api/nexus/*` requires loopback origin (`127.0.0.1` / `::1`)
- **TLS everywhere** — self-signed cert auto-generated; import once into browser
- **Secret files never served** — `.env`, `.key`, `.pem`, `.secret` blocked at the file server level regardless of location
- **CSP headers** on all responses
- **`~/NeXuS/secrets/nexus.env` is never committed** — listed in `.gitignore`

---

## Troubleshooting

**Port in use on start**
```bash
fuser -k 8443/tcp
python3 server/nexus_web_server.py --root web
```

**Browser shows "Blocked" or connection refused**
```bash
curl -sk https://localhost:8443/api/health
```
If no response — Bifrost isn't running. If JSON returned — browser cert issue, re-accept the self-signed cert.

**OC: `DatabaseClosedError VersionError` on load**

The browser's IndexedDB has a schema from a newer OC version. Clear it:
```javascript
// F12 → Console on https://localhost:8443/oc/index.html
indexedDB.deleteDatabase('chatbot-ui-v1').onsuccess = () => location.reload()
```

**Provider key not being picked up**
```bash
curl -sk https://localhost:8443/api/health | python3 -m json.tool
```
Keys are read per-request (no restart needed). Priority: process env > `nexus.env`.

**OC streaming broken after server update**

Hard-reload (`Ctrl+Shift+R`) to get fresh injected script. Clear IndexedDB if prompted.

---

## File Structure

```
nexus-bifrost-bridge/
├── server/
│   ├── nexus_web_server.py   ← entire server (single file, ~3600 lines)
│   ├── cert.pem              ← auto-generated TLS cert (gitignored)
│   └── key.pem               ← auto-generated TLS key (gitignored)
├── web/                      ← static web root
│   ├── index.html            ← NeXuS hub
│   ├── oc/                   ← OpenCharacters
│   ├── nncc/                 ← Network Command Center UI
│   └── ...
├── nncc/                     ← NNCC FastAPI backend source
├── docs/
│   └── action_report.md      ← per-task change log
├── bifrost.initd             ← OpenRC init script
├── .gitignore
└── README.md
```

---

## License

NeXuS project — hackenstacks@protonmail.com  
*Together Everyone Achieves More — Sane · Simple · Secure · Stealthy · Beautiful*
