# Launch copy / 发布文案

[English](ANNOUNCEMENT.en.md) · [中文](ANNOUNCEMENT.zh-CN.md)

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


---

# SoloPup Subtitle Studio — 公开预览版

[English](PRODUCT.md) · [中文](PRODUCT.zh-CN.md)

由 SoloPup 开发。面向 SDH 无障碍字幕，以及跟随中文配音的英文字幕制作的本地工作台。

## 两大核心亮点

- SDH 无障碍字幕：对照原片审校对白、说话人、重要音效、音乐及声音表现。
- 中文配音配英文字幕：中英同屏对照，跟随中文断句与信息顺序，用节奏和音节估算辅助审校。

面向独立创作者、字幕编辑、无障碍审校者与本地化团队。统一管理剧集、保存修改历史、逐句回放，分别导出 ITT 或 SRT。

## 从已有字幕开始

导入屏数、时码对应的中英 SRT，即可不使用 AI 账号进行本地审校。AI 初稿制作需要自己的 Qwen API Key 与模型权限。先核对适用试用额度，用真实对白小片段评估，再准备批量计费与预算。通常同一个 Key 从试用继续用于付费调用。

[安装与离线试用](QUICKSTART.zh-CN.md) · [Qwen 配置](QWEN_SETUP.zh-CN.md) · [费用与隐私 FAQ](FAQ.zh-CN.md)

## 实际界面

以下为使用合成演示数据的实际运行截图，只有播放器场景画面由 AI 生成。字幕为导入的示例文字，与演示视频中的发音不对应，不能证明识别或翻译质量。界面指标与待审核状态真实显示，截图使用中文控件。

![中英字幕校对：对应时码、CPS 读速与音节估算](screenshots/bilingual-review.jpg)

中文配音配英文字幕：两轨同时显示，核对对应时码，参考音节估算。

![SDH 声音候选、原声波形、短音频与人工判断操作](screenshots/sdh-sound-review.jpg)

SDH 声音判断：试听合成候选，定位原片，再决定保留、修改或删除。

![项目工作方式、独立审核进度与 SRT 导出](screenshots/projects-and-export.jpg)

项目管理与导出：按项目选择工作方式，保留独立审核进度，导出 ITT 或 SRT。

## 预览版范围

2.0.0-rc.5 为 MIT 许可的公开预览版。运行需要 Python 3.9+、FFmpeg/ffprobe 与现代浏览器。macOS 已在本机验证，Windows/Linux 尚未完成同等级人工验收。双语编辑页使用中文控件，输出仍需人工音画批准；程序检查不代表平台认证。

[SDH 工作方式](SDH.zh-CN.md) · [中英双语工作方式](BILINGUAL.zh-CN.md) · [版本说明](RELEASE_NOTES.zh-CN.md)
