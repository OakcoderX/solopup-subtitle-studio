# Video-system module boundaries

SDH Studio is the subtitle/review module of a larger video-production system. It can run independently. It does not generate source films or alter picture/audio. Other video tools may exchange media paths, script references and exported subtitle artifacts through its CLI and local APIs.

- `start_workbench.py`, `bootstrap.py`, `scripts/doctor.py`: local runtime, readiness and restart entry points.
- `workbench/library.py`: persistent projects, separate episode revisions and resumable worker queue. Source files are linked by fingerprint; revisions stay separate.
- `workbench/produce.py` and review/repair helpers: recognition, reference comparison, whole-episode evidence, timing and review proposals. Provider access uses configurable local endpoint/models; user keys are not source assets.
- `workbench/server.py`: loopback HTTP service. Public edition is intended for a single trusted local user; it has no multi-user authentication and must not be exposed directly to the internet.
- `workbench/index.html`: existing editor, state tokens and audio/video interaction.
- `workbench/studio.js`: project and review tools. `shell_policy.js`: episode-version grouping. `shell.js`: persistent drawer, fixed actions and export dialog. `studio.css`: fixed header, independent panes and responsive sizing.
- `workbench/export_bundle.py`: read-only, per-project/episode export snapshots; source checks and content remain unchanged. Offsets are required to align exactly to frames. Exported bundles record source-state hashes and REVIEW_DRAFT status when gates remain unresolved.
- `workbench/quality_gate.py` and technical/evidence modules: shared checks. “Ready” is a local result, never official editorial acceptance.

Runtime data and optional private project knowledge live outside public code. Existing state/sound files and SQLite records are not migrated or rewritten by a shell upgrade. New UI preferences live in browser local storage and do not change subtitle content. A service process must remain running for playback, saves, waveforms and background work; Codex need not be actively reasoning for review to function.

To integrate another editing tool, preserve final-master identity, frame rate, source vs delivery timebase, track kind, revision and approval status. Do not flatten them into a filename or a single “passed” boolean.
