# MediaGrid

The [REA implementation record](docs/REA-IMPLEMENTATION.md) tracks the six-mode
studio work, baseline evidence, migration status and remaining acceptance gates.

O [plano e a auditoria do Atelier Premium v3](docs/ATELIER-PREMIUM-V3.md)
documentam a branch visual atual e seus limites funcionais.

MediaGrid V1 is being built as a local **Windows desktop application**. Tauri hosts the
React panel in its own window and starts the FastAPI Core and worker on the same computer.
See [DESKTOP-PLAN.md](DESKTOP-PLAN.md) for the delivery gates. The Windows CI installs the
desktop package and renders a short MP4 with video and audio. A hands-on check on a clean
Windows PC remains required before treating this as a finished V1. The localhost script
remains a development fallback.
The panel logo is an original SVG based on the supplied MediaGrid visual reference.

The first pilots are YouTube Football, TikTok Geography and Instagram Music. The core stays
independent of niches: niches are engines, platforms are connectors, and visual styles are
template packs.

The renderer uses text cards or a selected local image/video behind the scene text. Windows offline speech synthesis can add narration to the MP4;
the library can use bundled faster-whisper on CPU for editable word timings and approved
captions. The older plain-text transcription path uses Windows speech recognition or an
optional local whisper.cpp model. The
Politics Radar can read public Câmara dos Deputados PL records with no account or API key.
Other research, fact verification, licensed asset sourcing, and direct publishing are still
manual.

## Creating a useful first script

Create a channel, then a project. In **Pauta / briefing**, enter three to five concrete
statements on separate lines (20–300 characters each). The local plan copies those statements
into editable scene narration without adding facts. Review and save the script in the Editor,
generate local voice if available, then render and review the MP4. A short topic instead
produces an editorial outline. Voice and render stay blocked until the narration of every
outline scene has been edited and saved.
The Editor identifies whether the plan came from the brief, an official source, local AI,
or manual edits. For a Politics channel, open **Radar**, search Câmara PLs by year and
optional ementa term, inspect the source link, and choose **Criar roteiro**. MediaGrid
fetches the selected PL again, stores the official source URL and retrieval time in the
project plan, and creates an editable vertical script from the identifier, ementa, and last
recorded status. The API is online and may be unavailable; the saved project remains local.
The source is evidence to review, not proof that a proposal became law. Check the current
tramitação, context, and media rights before approving the manual export.
When a Politics channel is selected in **Nova produção**, the default action opens this
official search. A manual political draft remains possible, but every political project
requires cited, approved claims before review and export, including older drafts.
The [isolated Politics pipeline proof](docs/POLITICS-TECHNICAL-PROOF.md) records a
live Câmara import, local voice, vertical MP4, hashes and the blocked export.
For a Geo channel, **Radar** can import a municipality from the
[IBGE Localidades API](https://servicodados.ibge.gov.br/api/docs/localidades).
The saved draft now creates one source-linked claim for each factual scene. The
API does not provide a publication date for that municipality record, so the
claim leaves it empty and records the consultation time separately. Verify each
claim against the live source before approving the render; new Geo and Trends
reviews require citations. Already approved Geo/Trends exports keep their prior
review if untouched. See [Geo evidence gate](docs/GEO-EVIDENCE-GATE.md).

For a Trends channel, **Radar → Trends · leituras na Wikipédia** imports a dated
[Wikimedia pageview report](https://doc.wikimedia.org/generated-data-platform/aqs/analytics-api/reference/page-views.html).
The draft states recorded views and rank on Portuguese Wikipedia with individual
source claims. These are Wikipedia page requests, not Instagram analytics or
proof of a wider trend. See [Trends evidence](docs/TRENDS-WIKIMEDIA.md).

For a Geo channel, **Radar** searches the official [IBGE Localidades API v1.0.0](https://servicodados.ibge.gov.br/api/docs/localidades) by municipality name and creates an editable three-scene plan from the selected municipality, state and administrative regions. It stores the source URL and retrieval time, and the render labels the source as IBGE. This flow does not supply maps, population data or licensed footage. Review the current IBGE entry and add your own rights-cleared visuals in the Editor.

In **Biblioteca**,
import your own JPEG, PNG, WebP or MP4, or record its license; then choose it in each scene's
**Mídia da biblioteca** field in the Editor, inspect the preview, and save. Unknown/restricted rights block saving
or rendering. Licensed media needs a recorded license name. Selected MP4s are muted under
the narration. For each MP4 scene, enter an optional start and end time in seconds; the selected
range repeats if the scene is longer than that range. The source clip's own audio is muted. A rendered MP4 can be
reviewed and downloaded, then packaged for manual publication after human approval. The
review form lets you edit an Instagram caption; the ZIP includes `caption.txt` alongside
`video.mp4` and the audit manifest.
The Editor can add or remove scenes while keeping at least two. A draft with an empty scene
narration can be saved, but voice and render wait until every scene has narration.
When a generated WAV lasts longer than the estimated scene times, the renderer extends the
video scenes to keep the full narration audible. Generating a new voice or render after review
invalidates the old approval until the new video is reviewed.

In **Editor → Saída**, the desktop can also capture microphone audio (where the WebView
supports it) or import your own WAV/MP3/M4A/WebM/OGG recording. Listen to the selection,
confirm that you own its rights and that it follows the saved script, then choose **Usar esta
narração no projeto**. The local API verifies an audio stream (0.2 seconds to 5 minutes;
50 MB upload limit), converts it to 48 kHz mono PCM WAV with FFmpeg, records hashes and
human attestations, and uses that WAV in the existing render worker. Changing the script
invalidates the recording; replacing voice after review invalidates the previous approval.
No automatic word alignment or audio quality approval is claimed. The system voice option
remains available. See [recorded voice implementation](docs/RECORDED-VOICE.md).

For a video or audio asset, open **Biblioteca → Legendas**. Run offline word ASR, listen
to the media and correct words, cue text and timing. Save and approve the current revision
before downloading SRT/VTT. For a rights-cleared MP4, **Gerar MP4 legendado** starts a
local FFmpeg job; the download appears after it succeeds. Edits invalidate approval and
the previous captioned MP4. In development, install `uv sync --extra asr` and point
`MEDIAGRID_ASR_MODEL_DIR` to an existing faster-whisper model folder. The Windows
installer bundles a pinned base model for offline use; no inference account is needed.
This flow is technical and requires a full human listen/watch before publication.

For a rights-cleared video with an approved timed transcript, open **Biblioteca → Cortes**.
**Analisar fala** stores explainable speech-window suggestions, their source hash and
surrounding context. Listen to the original, adjust the in/out points and vertical
crop if needed, save the edit, then explicitly select a candidate. **Renderizar
corte** creates a captioned MP4 with source audio; download is offered only for
the current selected revision after the worker verifies the file hash. A changed
transcript or source invalidates older cuts. The score orders speech windows; it
does not measure editorial quality or predict reach. Review every frame and the
full audio before publishing. Without owned or licensed footage, use synthetic
media only for technical testing.

In a saved project, use **Editor → Cartões em movimento** to add a versioned
title/body card to a scene. Edit its text, color, layout and timing, then save
the EDL revision. The Remotion preview and MP4 use the same card props; the
existing local voice and licensed music/SFX tracks can be mixed with it.

For an original animated advertisement, choose **Nova produção → Motion Ad**
and supply four distinct messages plus the product, audience and brand color.
MediaGrid saves an editable script and two animated cards, renders with the
existing local worker and requires cited claims and human review before manual
export. It does not create or verify marketing promises. See
[Motion Ad brief](docs/MOTION-AD-BRIEF.md).
Changing the card invalidates the previous render and editorial approval.
This is one motion component, not a complete automated ad or explainer.
Use **Editor → Diagrama de ideias** to add a conceptual two to four step flow.
Its labels, title, color, timing and visible credit are saved with the EDL;
the preview and MP4 animate the same sequence. Add source URLs in human review
when the diagram makes factual claims. Without a source, the video labels it a
conceptual diagram and blocks manual delivery until the existing source review.

For a Football channel, open a project and use **Editor → Football Edit**.
Import owned or licensed video first. Mark the original in/out points and event
roles by hand, choose a crop focus and optionally enter a sourced score. A replay
must refer to an earlier action with the same verified event ID. Save the
revision, explicitly confirm events and rights, then render. The local worker
creates an MP4 from the pinned source hashes, labels replay, and retains source
audio. Download is available only for the current approved revision. This
tool does not recognize goals or players, choose music, or publish automatically.
Inspect the entire export before use; without authorized footage and music,
only synthetic technical tests are possible.

For a factual explainer in a Geo, Politics or Trends project, use
**Editor → Alegações e fontes**. Attach each factual statement to a scene,
source URL, publication date when the source provides it, and the supporting
excerpt. Open the source and
confirm its context before approving that individual claim. Adding a claim
turns the project into a knowledge explainer: final review requires every
current claim approved and its URL in the source list. The Editor adds the
claim URLs to the final review request automatically. The manual export
records the reviewed claim ledger and its digest. Editing or removing a claim,
or changing the script or timeline, revokes the relevant review. MediaGrid
does not verify truth by itself or fetch arbitrary URLs on the user's behalf.

The Editor also includes **Personagem 2D · Migo**. It is an original SVG rig
whose speech bubble, expression, pose, color and mouth cues are saved in EDL v2.
The same Remotion component drives the Player and local MP4. Mouth cues are
placed manually against audio; MediaGrid does not detect phonemes or certify
lip sync. Use `uv run python scripts/prove_video_pipeline.py --character-2d`
for an isolated technical proof, then inspect the full audio and video before
using the character in an editorial piece.

For **Narrativa 3D**, create a project in that mode and open its Editor. Write
three to eight distinct story beats, choose action, camera, light and duration,
then save the storyboard. Configure a local **Blender 4.5 LTS** executable in
Settings or set `MEDIAGRID_BLENDER_PATH`. The worker first renders a low resolution
blocking MP4. Watch the full preview and explicitly confirm character continuity
and timing before requesting the full resolution final MP4. A changed storyboard
invalidates both renders and the approval. Without Blender the queued job stays
`WAITING_FOR_WORKER`; the renderer never reports success for an absent file.
The original Migo rig and Atelier stage are procedural; each render pins their
script hash and the storyboard hash. A local owned or licensed audio asset may be
selected if it covers the whole story. Otherwise the MP4 has an identified silent
AAC track. This first 3D mode does not yet supply acting, dialogue generation,
sound design, or an editorially approved film. Inspect the full audiovisual export
before delivery. Blender is an optional separate GPL installation; it is not
bundled in the MediaGrid installer.

## Current development fallback on Windows

See [SETUP.md](SETUP.md) for installation and troubleshooting. On Windows, double-click
`Iniciar-MediaGrid.cmd`. Or, in PowerShell from the project folder:

```powershell
.\scripts\bootstrap.ps1
.\scripts\dev.ps1
```

Keep the PowerShell window open and visit **http://localhost:3000**. The API docs are at
**http://localhost:8000/docs**. Files and automatic daily SQLite backups live under `data/`.

## Other development systems

```bash
cp .env.example .env
./scripts/bootstrap.sh
./scripts/dev.sh
```

Open the web app at `http://localhost:3000`. The API documentation is available at
`http://localhost:8000/docs`.

The default database is SQLite. A future server migration may use PostgreSQL, but no VPS,
cloud service or account is required for V1. Paid AI and cloud integrations are off by default.

## Principles

- Local services are the default; paid AI is disabled by default.
- Ollama on localhost can improve narration in the plan; a built-in plan works without it.
- The worker renders media, generates local speech, transcribes locally and backs up SQLite.
- Every external publisher defaults to dry-run.
- Assets retain rights metadata; unknown or restricted assets require review.
- Work is persisted as observable, retryable jobs.
