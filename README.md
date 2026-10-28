# SoloPup Subtitle Studio

[CI configuration](docs/ci/checks.yml) · [MIT](LICENSE) · [Download](https://github.com/OakcoderX/solopup-subtitle-studio/releases) · [Website](https://oakcoderx.github.io/solopup-subtitle-studio/)

**Developed by SoloPup. A local subtitle workspace built around two core strengths: SDH accessibility captions and English subtitles for Chinese-language audio.**

[中文说明](README.zh-CN.md) · [Get started](#get-started) · [AI coding assistant rules](AGENTS.md)

Bring transcription, translation, timing review and export into one project. Work with ordinary subtitles and SDH accessibility captions, or review Chinese dialogue alongside its English translation. Keep the final video in view, compare individual cues, and retain the evidence and editing history behind each draft.

SoloPup runs locally in a browser. You can use the editor yourself or ask Codex to help prepare and check a project. Importing existing subtitle files and reviewing them does not require an AI account.

## Two core strengths

### SDH: bring the sound of the story into the captions

SDH (Subtitles for the Deaf and Hard of Hearing) is one of the system’s main strengths. Beyond dialogue and lyrics, accessible captions need to communicate relevant speaker identity, meaningful sound effects, music and vocal delivery, so viewers can follow the story and its emotional cues without relying fully on sound.

The workspace organizes ordinary subtitles and SDH as separate tracks. Sound evidence and human review help determine which sounds matter, how to describe them accurately and when their captions should appear. Review individual cues against the video and retain editing and review history. AI proposes candidates; a human reviewer confirms the sound interpretation.

### Chinese audio, English subtitles: follow the original performance

Localize content for English-speaking viewers while keeping its Chinese soundtrack. First align the Chinese transcript to the spoken audio, then translate it screen by screen. Display both tracks over the video to check the source, translation and timing together.

English screen changes should follow Chinese dialogue breaks and reveal information in the same order. Aim for comparable spoken length, rhythm and syllable count while preserving meaning and natural English. For example, a Chinese sentence spoken across two subtitle screens should preferably have two corresponding English screens, rather than revealing the whole sentence early.

Estimated syllable counts and differences support review; they are not lip-sync verification or a strict requirement for identical counts. Bilingual imports require matching screens and times. Export Chinese and English as separate ITT or SRT files.

## What you can do

- Organize episodes and draft versions through a shared project page and background queue. Add one to five episodes per batch; pause, retry or create a separate new draft.
- Watch video while comparing source and translated text. Replay a cue, loop a passage, change playback speed or step through the subtitle editing frame grid.
- Check reading speed, line length, duration, gaps and overlaps, using each project's saved profile. Source video frame rate and subtitle editing frame rate are recorded separately.
- Save edits and review decisions with version-conflict protection. A stale page cannot silently overwrite a newer saved version.
- Export ITT or SRT tracks separately. Bilingual exports retain the original video filename with `.zh` and `.en` language suffixes.
- Use a compact, original Markdown reference for Chinese, English, Japanese and Korean rules and their implementation status. Reference coverage is broader than automatic production support.

## Set up Qwen before AI production

Cloud AI production requires your own Qwen API key and accessible models. First check applicable trial quota and evaluate a short clip; prepare provider billing and budget before regular batch work. Usually the same key is used for trial and paid usage. [Qwen application and trial-to-production guide](docs/QWEN_SETUP.md).

Import both Chinese and English SRT files for a fully offline bilingual workflow. To generate drafts, optional local Faster Whisper can transcribe Chinese audio, and a configured text model can translate individual screens. The ordinary subtitle/SDH workflow also includes optional provider-assisted recognition and review.

Provider settings are entered locally. Saving them makes no model request and does not verify account access. When you run cloud processing, the selected audio, images, script references or text needed for that task are sent to the provider you configure. Review without cloud processing keeps those contents local. Local ASR requires separately installed dependencies and downloaded model weights.

## Get started

Requirements: Python 3.9+ (3.11+ recommended), FFmpeg/ffprobe, and a modern browser. macOS has been tested locally. Windows and Linux have not completed the same manual acceptance pass.

```sh
python3 bootstrap.py --install
.venv/bin/python scripts/doctor.py --json
.venv/bin/python scripts/make_demo.py
.venv/bin/python start_workbench.py --video examples/demo/generated/demo.mp4 --standard-srt examples/demo/normal.srt --sdh-srt examples/demo/sdh.srt --port 8877
```

On Windows, use `.venv\Scripts\python.exe` instead of `.venv/bin/python`. Open `http://127.0.0.1:8877/projects`, create a project and choose its workflow before importing episodes. Keep the terminal/server running while you work. The sample is synthetic and silent; it demonstrates the editor, not transcription accuracy.

For your own media, replace the demo path with a local video. Existing projects and edits remain local under `Subtitle_Library/` and `Subtitle_Projects/`; back these up together with linked media. Reconnecting a different master requires a fresh timing check. The public package contains no real productions, character lists, screenplays, song recordings or editing databases.

If you use Codex, open the extracted folder and ask it to read `AGENTS.md` first. If you use the editor directly, start from the project page. See [Quick start](docs/QUICKSTART.md) and [Development guide](docs/DEVELOPMENT.md).

## Scope and limits

Automatic production interfaces currently accept English US/UK targets, including Chinese-to-English localization. Japanese and Korean Markdown references do **not** mean verified Japanese/Korean automatic production is available. The bilingual editor currently uses Chinese control labels; interface localization is separate from subtitle-language support.

The English profile and bilingual profile are different. Bilingual defaults use a 17 CPS target and a 21 CPS project ceiling; that ceiling is not a universal children's platform specification. Confirm the recipient's current language and title-specific requirements before delivery.

A saved file, a machine opinion, a format check and human audiovisual approval are separate states. Exports remain review drafts when work is unresolved. Local checks do not establish translation accuracy, precise synchronization, accessibility quality or platform acceptance. This is a trusted local-user application, not an internet-facing multi-user service. No account signup, subscription or hosted service is bundled.

## Development and license

```sh
python3 -m unittest discover -s tests
node --test tests/*.cjs
```

Tests use temporary projects and synthetic data, without paid AI calls. A GitHub Actions configuration is supplied at `docs/ci/checks.yml`. Installing it under `.github/workflows/` requires workflow permissions. Remote CI has not run for this release.

Code and original general documentation are MIT licensed; see [LICENSE](LICENSE) and [LICENSE_SCOPE.md](LICENSE_SCOPE.md). Third-party platform manuals, schemas and private project knowledge are excluded. Obtain authoritative delivery documents from their owners. Provider and platform names describe interoperability, not endorsement.

**Release:** 2.0.0-rc.5, a public preview candidate. See [release notes](docs/RELEASE_NOTES.md).
