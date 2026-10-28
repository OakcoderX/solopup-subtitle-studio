# Chinese audio, English subtitles

[English](BILINGUAL.md) · [中文](BILINGUAL.zh-CN.md)

Keep the Chinese soundtrack. Let English-speaking viewers follow the original performance, one subtitle screen at a time.

## Source first, translation alongside

First align the Chinese transcript to the final audio, then translate screen by screen. Display both tracks with the video to check meaning, terminology, natural English and timing together. Scripts are references; they are not proof of what is actually spoken.

## Follow dialogue breaks and reveal order

If a Chinese sentence is spoken across two subtitle screens, prefer two corresponding English screens. For example, screen 1: “先别开门。” / “Don’t open the door yet.” Screen 2: “我听见外面有声音。” / “I hear something outside.” This invented example shows reveal order, not measured timing or model quality.

## Comparable length and rhythm

Aim for comparable spoken length, rhythm and syllable count while preserving accurate meaning and natural English. Do not pad a translation to reach a number. Estimated syllables and differences are advisory; they are neither exact lip-sync verification nor a strict identical-count export gate.

![Chinese and English tracks with corresponding cue times, syllable estimates and CPS](screenshots/bilingual-review.jpg)

The screenshot uses imported illustrative text, with both tracks still pending human review. The demo movie has no matching spoken dialogue, so it is not an ASR or translation benchmark. Only its artwork is AI-generated.

## Import, review and export

1. Create a Chinese-audio bilingual project. For offline review, supply a local video and Chinese/English SRT files with matching screen counts and times.
2. Review source transcription and translation separately; compare reading speed and timing against the real audio.
3. Save decisions. The bilingual default target is 17 CPS, with a 21 CPS project ceiling; this is not a universal platform rule for children.
4. Export separate .zh and .en ITT or SRT files using the original video filename. Put them beside the matching video for player discovery.

## Current support

The bilingual editor currently uses Chinese control labels. Automatic production targets English US/UK. Japanese/Korean reference summaries do not establish verified automatic production support. Cloud translation needs your own Qwen key and model access; optional local Chinese ASR needs separately installed dependencies and multilingual weights.

[Get started](QUICKSTART.md) · [Qwen setup](QWEN_SETUP.en.md) · [Scope and privacy](FAQ.md)
