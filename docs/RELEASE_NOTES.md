# Release notes: 2.0.0-rc.5

[English](RELEASE_NOTES.md) · [中文](RELEASE_NOTES.zh-CN.md)

Public preview · Developed by SoloPup · 2026-10-28. Current product documentation is available in English and Chinese.

## Two core strengths

- SDH accessibility captions: separate ordinary and SDH tracks, meaningful sound candidates and evidence-based human review.
- Chinese audio with English subtitles: same-video dual-track review, corresponding screen breaks and advisory length/syllable checks.

## Included in this preview

- Unified project entry and local background drafts; separate saved workflow settings.
- Revision history, explicit saving and stale-version protection.
- Separate ITT/SRT exports; original-video naming with language suffixes for bilingual files.
- Qwen first-use guidance and key-presence checks before cloud jobs enter the queue. No automatic model test or billing activation.
- Original Chinese/English/Japanese/Korean reference summaries with official links and implementation limits.

## Validation and current limits

259 Python tests and four JavaScript tests passed locally on the launch source. Offline synthetic-media import, saving and exports were checked. These are software checks, not proof of language or accessibility quality. Remote test CI has not run for the launch; the workflow template is under docs/ci/.

Automatic targets are English US/UK. macOS has local verification; equivalent Windows/Linux manual acceptance is incomplete. The bilingual editor uses Chinese controls. Model access needs your own account/key. Human audiovisual review remains required; no platform certification is implied.

## Public contents and documentation update

The release excludes private productions, character libraries, customer review histories, credentials, original third-party manuals and schemas. Screenshots use synthetic examples and original AI-generated movie artwork. The English/Chinese product pages, full guides and screenshot captions are documentation updates on main; the original release tag and downloadable archive are unchanged.

[Download the preview](https://github.com/OakcoderX/solopup-subtitle-studio/releases/tag/v2.0.0-rc.5) · [Quick start](QUICKSTART.md) · [FAQ](FAQ.md)
