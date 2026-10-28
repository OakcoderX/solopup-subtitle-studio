# Cost, privacy and support FAQ

[English](FAQ.md) · [中文](FAQ.zh-CN.md)

Know what runs locally, what needs a provider and what the preview has actually verified.

## Is it free?

The code and original general documentation are MIT licensed. Reviewing existing subtitles locally needs no AI subscription or account. Cloud recognition, translation and review use your own provider account and may incur charges. Applicable trial quota is controlled by the provider; SoloPup does not issue keys or grant credits.

## Does my video leave my computer?

Review without cloud processing keeps content local. When you start a cloud task, the required audio, images, script references or text are sent to the provider you configure. Saving provider settings makes no model call. Local ASR needs separately installed dependencies and downloaded weights.

## How is my API key handled?

Enter it yourself in local settings. The key is stored locally as plaintext with owner-only permissions where supported, not in an OS keychain; it is excluded from browser storage, Git and release archives. Never post it in chat, issues or command arguments. A configured key does not prove model access, balance, trial eligibility or billing readiness.

## What can I export?

Separate SRT and ITT tracks. Bilingual exports use .zh and .en suffixes and preserve the original video filename. Confirm the recipient’s current title/language requirements and inspect the exported file. Choosing a profile is not platform certification.

## Which languages and systems are supported?

Automatic production targets English US/UK, including English subtitles for Chinese audio. Four-language Markdown references cover Chinese, English, Japanese and Korean, but Japanese/Korean automatic production is not verified. The bilingual editor uses Chinese controls. Python 3.9+, FFmpeg/ffprobe and a modern browser are required. macOS has local verification; equivalent Windows/Linux manual acceptance is incomplete.

## Does syllable matching mean dubbing or lip sync?

No. Comparable length and rhythm are translation review goals. Estimated syllables are advisory. The Chinese soundtrack is retained; the system does not promise exact lip sync or identical counts. Accurate meaning, reveal order and natural English remain essential.

## Is this a stable or certified release?

Version 2.0.0-rc.5 is a public preview. Source transcription, translation, timing and SDH quality need human audiovisual review. Local software and format checks are not final acceptance. Remote test CI has not run for the initial release; a configuration template is supplied under docs/ci/. This is a trusted local-user app, not an internet-facing multi-user service.

## How do I report a problem?

Use [GitHub Issues](https://github.com/OakcoderX/solopup-subtitle-studio/issues). Include the version, OS, expected behavior, actual behavior and a minimal synthetic example. Do not attach credentials, private productions, unreleased scripts or customer review histories. [Get started](QUICKSTART.md) · [Qwen setup](QWEN_SETUP.en.md) · [Release notes](RELEASE_NOTES.md)
