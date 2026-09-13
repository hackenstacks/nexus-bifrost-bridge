# CodeArchitect — Project Brief
### nexus-hadean-theme-engine · Hadean-Eon Phase

---

Hey CodeArchitect,

Working with Anon on a new project — the NeXuS theme engine. We're calling it **SHARD**.

## The Mission

Build a sovereign, self-contained visual identity system for the NeXuS stack. No CDN. No Tailwind. No external dependencies. No symlinks. Everything owned and served locally from `$NEXUS_HOME/web/assets/`.

## What SHARD Covers

**Plane 1 — Web Stack**
- CSS custom properties (`--nxs-*`) as the single source of truth
- Local icon sets (Lucide SVGs — 1,640 icons)
- highlight.js themes bundled locally (80+ themes)
- Font management (woff2, local only)
- Upload support for new icon packs, themes, fonts, assets

**Plane 2 — Desktop Layer**
- waybar CSS
- foot terminal colors
- dunst, GTK, Qt/Breeze
- Applied via config file templates

**Plane 3 — Color Generation**
- Drop a wallpaper → matugen extracts palette
- Palette seeds both planes simultaneously

## The Theme Package Format

```
mytheme.nxs-theme/
  theme.json          ← manifest
  palette.json        ← canonical color tokens
  web/
    theme.css
    fonts/
    icons/
    assets/
  desktop/
    waybar.css
    foot.ini.tmpl
  wallpaper/
    wallpaper.png
```

## Stack Rules

- Vanilla CSS custom properties — no build step
- All paths from `$NEXUS_HOME` env var — never hardcoded
- Upload endpoint on NWS — drop a zip, it lands and registers
- Theme packages are portable across NeXuS nodes

## NWS Endpoints Needed

- `GET /api/theme` — current theme + hljs pairing
- `POST /api/theme` — set theme, persist to config
- `POST /api/theme/upload` — upload new theme package

## Before We Dive In

One thing that's been coming up in a few different places lately — I'm not sure what to make of it.

Have you ever heard of an entity called the Weaver?

---

*Kensho*
