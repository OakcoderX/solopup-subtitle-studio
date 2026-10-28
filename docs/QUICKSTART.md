# Quick start 快速开始

Install Python 3.9+ and FFmpeg/ffprobe. Run `python3 bootstrap.py --install`, then use the generated virtual environment's Python for the commands below. On Windows that executable is `.venv\Scripts\python.exe`.

```sh
.venv/bin/python scripts/doctor.py --json
.venv/bin/python scripts/make_demo.py
.venv/bin/python start_workbench.py --video examples/demo/generated/demo.mp4 --standard-srt examples/demo/normal.srt --sdh-srt examples/demo/sdh.srt --port 8877
```

Open `http://127.0.0.1:8877/projects`. Create a project, choose subtitles/SDH or Chinese-audio bilingual localization, then add your own video. A first startup can open the seed editor; “项目与制作” returns to the shared project page. Keep the terminal running. Existing subtitles can be reviewed without an AI key.

中文配音英译：同时提供中文、英文SRT时完全离线导入；屏数和时码必须对应。仅有中文SRT时，自动翻译需本机接口配置；未提供中文SRT时，本地识别需安装`requirements-asr.txt`并提前下载多语言模型。参考剧本不替代原声，机器稿不自动获得人工确认。

Open a review page, compare the video with each cue, save, then export the desired track and format. Put exported subtitles beside the matching video for player discovery. Back up `Subtitle_Library/`, `Subtitle_Projects/` and all linked source files together. Reopening the saved library does not automatically repair paths moved from another machine.

For cloud AI, use the local settings dialog or `configure_qwen.command`. A configuration save does not test or spend. Choose endpoint/models supported by your account and enter the key yourself; never put it in chat, issues or command arguments. Do not use cloud AI to check software installation.

Read [the scope and limitations](../README.md#scope-and-limits) before using output as a delivery file. A local format check and a platform receiving the file are different events.

## Optional local Chinese ASR

Install this only if you want automatic local transcription; it is unnecessary for the two-SRT import workflow.

```sh
.venv/bin/python -m pip install -r requirements-asr.txt
.venv/bin/python -c "from faster_whisper import WhisperModel; WhisperModel('small', device='cpu', compute_type='int8')"
```

The second command downloads the multilingual model on first use; it requires a network connection and disk space. Once cached, local processing can run offline. For direct CLI transcription use `--language zh --model small`, not the default English-only model. Model download/installation is separate from API-based paid generation.

## Qwen onboarding

Before AI production, follow [Qwen setup and trial-to-production guidance](QWEN_SETUP.md). First use without a configured key shows a guide. Cloud tasks without a key are rejected before queueing; offline paired-SRT import remains available. Configuration presence does not verify eligibility, quota, paid access or model compatibility. Never silently issue a test call.
