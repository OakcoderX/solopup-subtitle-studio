# SoloPup Subtitle Studio — public preview

[English](PRODUCT.md) · [中文](PRODUCT.zh-CN.md)

Developed by SoloPup. A local workspace for SDH accessibility captions and English subtitles that follow Chinese dialogue.

## Two core strengths

- SDH accessibility captions: review dialogue, speakers, meaningful effects, music and vocal delivery with the original video.
- Chinese audio, English subtitles: compare source and translation together, follow source screen breaks and reveal order, and use advisory rhythm/syllable estimates.

For independent creators, subtitle editors, accessibility reviewers and localization teams. Organize episodes, save revision history, replay cues and export separate ITT or SRT tracks.

## Start with existing subtitles

Import matching Chinese/English SRT files for local review without an AI account. AI draft production needs your own Qwen API key and model access. Check applicable trial quota, evaluate a short real-dialogue sample, then prepare billing and budget for batch work. Usually the same key continues from trial to paid usage.

[Installation and offline trial](QUICKSTART.md) · [Qwen setup](QWEN_SETUP.en.md) · [Cost and privacy FAQ](FAQ.md)

## Inside the real workspace

These are actual application screenshots with synthetic demo data. Only the movie artwork is AI-generated. Imported example subtitles do not match spoken dialogue in the demo, so this is not an ASR or translation benchmark. Interface metrics and pending review states are real. Controls are shown in Chinese.

![Chinese and English subtitle review with matching cue times, CPS and estimated syllables](screenshots/bilingual-review.jpg)

Chinese audio / English subtitle review: both tracks, corresponding timing and advisory syllable estimates.

![SDH sound candidate, waveform, audio preview and human decision controls](screenshots/sdh-sound-review.jpg)

SDH sound review: listen to a synthetic candidate, locate it in the video and keep, revise or remove it.

![Project workflows, independent review progress and SRT export](screenshots/projects-and-export.jpg)

Projects and export: choose a workflow, retain separate review progress and export ITT or SRT.

## Preview status

Version 2.0.0-rc.5 is a public preview, MIT licensed. Python 3.9+, FFmpeg/ffprobe and a modern browser are required. macOS has local verification; Windows/Linux manual acceptance is incomplete. The bilingual editor uses Chinese controls. Human audiovisual approval remains necessary; local checks are not platform certification.

[SDH workflow](SDH.md) · [Bilingual workflow](BILINGUAL.md) · [Release notes](RELEASE_NOTES.md)
