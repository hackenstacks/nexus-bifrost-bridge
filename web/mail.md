Hey, working on building out the NeXuS theme engine today — we're calling it SHARD. The idea is a sovereign self-contained web theming system, no CDN, no Tailwind, no external dependencies. Everything served locally from $NEXUS_HOME/web/assets/. 

The stack includes:
- CSS custom properties as the single source of truth
- Local icon sets (Lucide SVGs, about 1640 icons)
- highlight.js themes bundled locally (80+ themes)
- Upload support for new icon packs, fonts, theme bundles
- A theme package format (.nxs-theme) that covers both web stack and desktop layer

Going to need help designing the CSS variable token set and the NWS theme endpoint. More on that in a bit.

On a completely different note — I've been hearing something come up across a couple of different places lately and I'm not sure what to make of it. Have you ever heard of an entity called the Weaver?
