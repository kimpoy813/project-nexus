# NExUS video tutorial — built with Remotion

A **programmatic video tutorial** for NExUS (Networked Extension Unified
System), written for a general audience: every office term is explained in
plain language, and every role's actual functions are shown. The video is
*written as code* — scenes are React components, animations are driven by the
frame number, and headless Chromium renders the finished MP4.

## Is this even possible? Yes — this folder is the proof

[Remotion](https://www.remotion.dev/) turns React into a video renderer:

- **React components are scenes.** A component reads the current frame via
  `useCurrentFrame()` and returns what the video looks like at that instant.
- **Hooks turn frames into motion.** `interpolate()` maps a frame range onto a
  value (opacity, position, width…), and `spring()` gives physics-based easing.
- **`<Sequence>` lays scenes on a timeline** — see [`src/Root.jsx`](src/Root.jsx).
- **`remotion render`** screenshots every frame through the Chrome DevTools
  Protocol and stitches them into an H.264 MP4.

Change a label in [`src/content.js`](src/content.js) and re-render — no video
editor, no re-recording.

## What the video covers

135 seconds at 1920×1080 / 30 fps (4,050 frames), nineteen scenes:

| # | Scene | What it teaches |
|---|---|---|
| 1 | Intro | NExUS identity (real logo) and what the guide covers |
| 2 | What is NExUS? | "Extension" explained; the three stages — proposal, agreement, delivery |
| 3 | Glossary | Twelve office terms in plain English (proponent, MOA, GAD, SDG, tracker…) |
| 4 | The seven roles | Who uses NExUS and the dashboard each one lands on |
| 5–11 | One scene per role | **Every function each role can actually do**, including Admin's limits |
| 12 | Dashboard mock | KPIs, progress ring, and the **+ New Proposal** button |
| 13 | Proposal wizard mock | The guided 20-section form, drafts, completion rail |
| 14 | Reviews & teamwork | Section comments, review rounds, evaluator assignment, co-editing |
| 15 | MOA tracker | The six agreement stages in plain language, plus "Not Required" |
| 16 | Implementation & reports | Six delivery stages, auto-generated paperwork, quarterly reports |
| 17 | Public website | The four public pages and the drag-and-drop, no-code content blocks |
| 18 | Safeguards | Email verification, idle logout, login lockout, maintenance mode… |
| 19 | Outro | The eight-step journey from *Create* to *Close* |

### Everything is sourced from the application

| Video content | Source in the Django app |
|---|---|
| Role functions and limits | `accounts/permissions.py` (capability matrix, report roles, object-level rules) |
| Role names | `accounts/models.py` → `User.ROLE_CHOICES` |
| 20 wizard sections | `proposals/views/constants.py` → `INITIAL_STEP_LABELS` |
| Extension types | `proposals/models.py` → `Proposal.ExtensionType` |
| Proposal statuses | `proposals/models.py` → `Proposal.ProposalStatus` |
| MOA / implementation stages | `proposals/models.py` → `MOA_FLOW`, `IMPLEMENTATION_FLOW` |
| Admin/no-code features | `accounts/urls.py`, `details/content_sources.py` |
| Logo | `static/images/nexus-logo.svg` (copied into `public/`) |
| Brand colors | `accounts/ui.py` → `BRAND_DEFAULTS` (`#103b07`, `#5a1113`, `#f5e587`) |

## Design system

The visual language is deliberately editorial rather than templated:

- **One grid.** `LAYOUT` in [`src/theme.js`](src/theme.js) defines the shared
  120 px side margins, 24 px gutter and 18 px radius; every full-screen scene
  aligns to the same left/right edges, and card grids use 12-column spans so
  rows of different counts (e.g. 6 stage cards above 4 reporting cards) line
  up exactly.
- **Calm surfaces.** Near-opaque panels with hairline borders replace frosted
  glass; entrance motion is a short opacity fade with a 14 px rise on one
  cubic ease — no springs, bounces, halos or drifting background layers.
- **Numerals over icon tiles.** Index numbers (`01`, `02`…) carry hierarchy
  instead of repeated pictogram boxes; glyphs are reserved for the product
  mockups and the few places a symbol carries meaning.

## Audio: music bed and voiceover

- **Music bed** — `scripts/make-music.mjs` synthesizes a 135 s ambient bed
  (`public/music/nexus-bed.wav`, 44.1 kHz stereo) with no external assets:
  detuned-sine pad chords, triangle sub-bass and sparse plucks through a
  low-pass filter. Re-run with `npm run music`; it is git-ignored because it
  is fully regenerable.
- **Voiceover** — the per-scene script lives in
  [`src/narration.js`](src/narration.js), sized to each scene's duration at
  the measured delivery rate (~3 words/second). Clips are generated externally
  into `public/narration/scene-XX.mp3` and **committed** because they cannot be
  regenerated offline. `scripts/sync-narration.mjs` writes
  `src/narration-manifest.json`; `Root.jsx` mounts only clips the manifest
  lists, so a missing line renders as a quiet music-only passage instead of
  breaking the build.
- **Ducking** — the bed plays at 0.24 and glides down to 0.09 while a
  voiceover line is expected, opening back up between scenes.
- After adding or replacing clips, run `npm run narration:scan` (the
  `prerender` hook does this automatically).

## Project layout

```
tutorial/
├── package.json              # scripts: dev / render / still / inspect / music
├── remotion.config.js        # renderer settings + headless-browser wiring
├── scripts/
│   ├── sync-fonts.mjs        # copies Inter woff2 from npm into public/fonts
│   ├── make-music.mjs        # procedural ambient music bed (offline WAV)
│   ├── sync-narration.mjs    # scans narration clips → narration-manifest.json
│   ├── prepare-browser.mjs   # offline headless-Chromium assembly (see below)
│   ├── inspect-mp4.mjs       # dependency-free MP4 codec/size/duration check
│   └── patch-studio-origin.mjs  # proxy-aware same-origin fix (postinstall)
├── public/
│   ├── nexus-logo.svg        # the real NExUS "Ni" monogram
│   ├── fonts/                # generated: Inter 400–800 (woff2, offline)
│   ├── music/                # generated: nexus-bed.wav (git-ignored)
│   └── narration/            # voiceover scene-XX.mp3 (committed)
├── src/
│   ├── index.js              # Remotion entry point (registerRoot)
│   ├── Root.jsx              # composition, 19-scene timeline, audio + ducking
│   ├── theme.js              # brand colors, LAYOUT/SURFACE/MOTION tokens
│   ├── content.js            # ALL on-screen text — glossary, roles, features
│   ├── narration.js          # voiceover script, one line per scene
│   ├── narration-manifest.json  # generated: which narration clips exist
│   ├── components/           # Fonts, Background, BrandMark, UI primitives…
│   └── scenes/               # one file per scene (RoleDetailScene is reused 7×)
└── out/                      # rendered MP4s and stills (git-ignored)
```

## Commands

```bash
cd tutorial
npm install                 # also runs the proxy-origin patch automatically
npm run dev                 # Remotion Studio: live editor at localhost:45761
npm run music               # regenerate the ambient music bed
npm run narration:scan      # refresh src/narration-manifest.json from public/narration
npm run render              # render out/nexus-tutorial.mp4 (1080p, H.264)
npm run render:hd           # faster 720p preview render
npm run inspect             # verify MP4 codec/size/duration/frames without ffmpeg
npx remotion still NexusTutorial out/check.png --frame=950   # one frame as PNG
```

`npm run render` runs the font sync, music synthesis, narration scan and
headless-browser setup first (via the `prerender` npm hook).

## Editing the tutorial

- **Wording, role functions, glossary, feature lists:** everything lives in
  [`src/content.js`](src/content.js) — start there.
- **Voiceover lines:** [`src/narration.js`](src/narration.js), one entry per
  scene; keep each line within the word budget noted at the top of the file,
  regenerate the clip into `public/narration/`, then `npm run narration:scan`.
- **Colors / fonts / spacing:** [`src/theme.js`](src/theme.js)
  (`COLORS`, `LAYOUT`, `SURFACE`, `MOTION`), kept in sync with
  `accounts/ui.py`.
- **Logo:** replace `public/nexus-logo.svg` (and the `LogoBadge`/`LogoRaw`
  components in `src/components/BrandMark.jsx` if the shape changes).
- **Scene length or order:** the `SCENES` manifest in
  [`src/Root.jsx`](src/Root.jsx). Durations are frames at 30 fps
  (e.g. `210` = 7 s); the composition duration is computed from the total.
- **Add a scene:** create `src/scenes/MyScene.jsx`, then add one manifest entry.
  The seven role scenes are one component (`RoleDetailScene`) driven by data.

## Headless browser in restricted environments

Normally Remotion downloads its own tested Chromium
(`npx remotion browser ensure`). In sandboxes where only the npm registry and
GitHub are reachable, that host is blocked. `scripts/prepare-browser.mjs`
instead installs `@sparticuz/chromium` from npm, unpacks its Brotli payload
with Node's built-in `zlib`, adds the NSS/SwiftShader libraries, and writes a
`chrome-wrapper`. `remotion.config.js` then points Remotion at it with
`chrome-for-testing` mode, `swangle` software GL, and multi-process on Linux.

Two gotchas the scripts handle deliberately:

- **Do not export `FONTCONFIG_FILE`** in the wrapper — the Lambda-oriented
  fontconfig shipped in the package points at `/var/task/...` and makes Blink
  reject every `@font-face` web font (invisible text).
- **Studio behind an HTTPS preview proxy:** Remotion's same-origin guard
  compares full origins, so proxied `https://…` requests to the internal
  `http://…` studio are rejected ("Request from different origin not
  allowed"). `scripts/patch-studio-origin.mjs` (run from `postinstall`) makes
  the check proxy-aware. It derives the effective public host from
  `X-Forwarded-Host`, then the RFC 7239 `Forwarded: host=…` parameter, then
  the `Host` header; compares hostnames and explicit ports instead of scheme
  + host; and accepts the browser's origin when a TLS-terminating proxy
  (`X-Forwarded-Proto: https` / `Forwarded: proto=https`) forwards to a
  loopback or private address. Genuinely cross-origin requests against a
  public host are still rejected, so DNS-rebinding protection is preserved.
  On a normal laptop you can delete this script and the `postinstall` entry.

## Outputs

- `out/nexus-tutorial.mp4` — the 1080p tutorial (H.264, ~135 s)
- `out/cover.png` — a still frame usable as a video thumbnail
