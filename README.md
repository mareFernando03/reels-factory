# Reels Factory

An Instagram Reels production pipeline operated from [Claude Code](https://claude.com/claude-code).
You drop in a **reference reel**, **instructions** (text or a WhatsApp voice note) and **raw clips**;
out comes a **ready-to-post reel**, with a caption, a cover, a quality report and a short message for
whoever publishes it.

Claude makes the creative calls (which takes, what text, what rhythm), always justified against a
written knowledge base. Deterministic Python tools do the mechanical work (cutting, beat-matching,
color matching, face-aware text placement, loudness, verification). A human approves the script
before anything is rendered.

> The code, docs and knowledge base are written in Spanish (Argentina), the language of the brands it
> was built for. The two brands included (`salon-demo`, `historia-breve`) are fictitious examples.

## How it works

```
reference reel ─┐                      ┌─► plan/guion.yaml ──(human OK)──┐
instructions ───┼─► analysis (beats, ──┤                                 ├─► render (HyperFrames)
raw clips ──────┘   cuts, faces, voice) └─► conocimiento/ (rules + rubric)┘        │
                                                                                   ▼
                                              QA: technical checks + rubric score ─► salida/
```

Every order lives in `pedidos/<date>-<brand>-<slug>/` as plain files (analysis JSON, script YAML,
render, output), so any step can be redone without repeating the previous ones. `fabrica.py`
fingerprints each step's inputs and only reruns what changed.

## Highlights

- **Beat-accurate editing**: tempo detection cross-checked against the reference's real cuts (librosa
  often confuses octaves and 2/3), cuts snapped to real beats, speed ramps and interpolated slow motion.
- **Face-aware titles**: YuNet face detection picks a title height that never covers a face; WCAG
  luminance behind each title decides between a soft shadow and highlighter blocks.
- **Brand system**: art direction as tokens (`estilo.py`); each brand overrides only what it declares in
  its `marca.yaml`, with no code changes.
- **Formats**: reels, Instagram stories, single photos and 3:4 carousels.
- **Audio**: three music modes (royalty-free track, synthetic bed, or in-app Instagram audio), voice
  detection with Whisper, vocal separation (MDX-Net) and -14 LUFS loudness.
- **Quality gate**: safe-zone checks (14/35/6), rhythm presets, `hyperframes check` with measured
  contrast, and a weighted rubric (`conocimiento/rubrica.yaml`) where blocking criteria must pass.
- **Knowledge base**: `conocimiento/` collects research on Instagram distribution, reel anatomy,
  branding, rhythm, audio and measurement, tagging each claim by evidence level (official / measured by
  third parties / industry practice).
- **Metrics loop**: read-only Metricool MCP import at 72 h and 7 days, aggregated per format.
- **Tests**: 120+ pytest tests, no media or network required, about 3 s.

## Requirements

- Python 3.12 with [uv](https://docs.astral.sh/uv/)
- ffmpeg 9 on the PATH
- Node.js (HyperFrames is run with `npx hyperframes@0.8.113`)
- Claude Code, with the HyperFrames and Remotion skills installed at project level from the sources
  listed in `skills-lock.json` (they are third-party and not included here)

## Quick start

```bash
uv sync
uv run pytest                      # tests
# in Claude Code:
/reel nuevo salon-demo mi-primer-reel
```

Then put the reference and raw clips in `pedidos/<order>/entrada/` and run `/reel <order>`. The full
operating guide is in [`CLAUDE.md`](CLAUDE.md) and the step-by-step skill in
[`.claude/skills/reel/SKILL.md`](.claude/skills/reel/SKILL.md).

To add your own brand, copy `marcas/salon-demo/` to `marcas/<your-brand>/` and fill in its identity,
colors, fonts and tone.

## Project layout

| Path | What it holds |
|---|---|
| `herramientas/` | Python tools: analysis, clip prep, composition, audio, QA, metrics |
| `conocimiento/` | Knowledge base, rhythm presets and the scoring rubric |
| `marcas/` | Brand identities (two fictitious examples, with open-license fonts) |
| `estilos/` | Reusable art-direction styles |
| `pedidos/_plantilla/` | Template for a new order |
| `musica/catalogo.yaml` | Royalty-free track catalog (audio files are downloaded on demand) |
| `tests/` | pytest suite |

## Third-party assets

- Fonts in `marcas/*/assets/fuentes/`: Google Fonts, SIL Open Font License.
- `herramientas/modelos/face_detection_yunet_2023mar.onnx`: YuNet from OpenCV Zoo, MIT.
- `herramientas/datos/ne_110m_land.geojson`: Natural Earth, public domain.
- Music: Mixkit Stock Music Free License tracks, downloaded from their source URL (not included).

## License

MIT © Fernando Mare
