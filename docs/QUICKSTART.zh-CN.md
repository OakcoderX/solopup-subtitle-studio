# 安装与字幕校对试用

[English](QUICKSTART.md) · [中文](QUICKSTART.zh-CN.md)

先用已有字幕体验，再配置云端 AI。以下步骤启动本地编辑器；自带的无对白合成示例只演示操作，不证明识别质量。

## 1. 下载并准备环境

[下载发布页中的 Public.zip](https://github.com/OakcoderX/solopup-subtitle-studio/releases/tag/v2.0.0-rc.5)，解压后在程序目录打开终端。先安装 Python 3.9+（建议 3.11+）、FFmpeg/ffprobe 及现代浏览器。首次安装依赖需要联网。macOS 已在本机验证；Windows/Linux 尚未完成同等级人工验收。

## 2. 生成示例并启动

```sh
python3 bootstrap.py --install
.venv/bin/python scripts/doctor.py --json
.venv/bin/python scripts/make_demo.py
.venv/bin/python start_workbench.py --video examples/demo/generated/demo.mp4 --standard-srt examples/demo/normal.srt --sdh-srt examples/demo/sdh.srt --port 8877
```

Windows 请把 .venv/bin/python 替换为 .venv\Scripts\python.exe。生成的视频为无对白合成示例，字幕只用于演示编辑操作，不代表实际发音或识别准确率。

## 3. 打开项目页

在浏览器打开 http://127.0.0.1:8877/projects。首次启动可能先显示种子编辑页，点击“项目与制作”返回项目页。使用期间保持终端／服务运行。新建项目，选择普通字幕／SDH 或中文配音双语本地化，再加入视频。

## 4. 离线校对已有字幕

双语校对时导入屏数、时码对应的中文与英文 SRT。两份文件都提供时，无需 API Key 或云端处理。只有中文 SRT 时，自动翻译需配置文字模型；没有中文 SRT 时，可按下方步骤安装本地识别。剧本不能替代最终原声。

![本地项目页：独立审核进度与 SRT 导出选项](screenshots/projects-and-export.jpg)

## 5. 保存、导出与备份

逐句回放、修改、保存，以 ITT 或 SRT 导出所需轨道。双语文件沿用原视频名称并加语言后缀。请把 Subtitle_Library/、Subtitle_Projects/ 及引用的原视频一起备份。跨电脑移动素材不会自动修复路径；更换母本后需重新校时。

## 可选：本地中文识别

仅在需要自动本地转写时安装；同时导入中英 SRT 的流程不需要这一项。

```sh
.venv/bin/python -m pip install -r requirements-asr.txt
.venv/bin/python -c "from faster_whisper import WhisperModel; WhisperModel('small', device='cpu', compute_type='int8')
```

第二条命令首次会下载多语言模型，需要联网和磁盘空间；缓存完成后，本地识别可以离线运行。直接使用转写命令时应指定 --language zh --model small，不使用默认英语专用模型。模型安装／下载与付费 API 生成分别处理。

## 云端 AI 制作前

先读 [Qwen 申请、测试与批量制作指南](QWEN_SETUP.zh-CN.md)。通过本机设置或 configure_qwen.command 输入自己的 Key。保存不调用模型，也不证明账号可用；未配置 Key 的云端任务会在入队前被拦截。先测真实对白小片段，再准备批量计费与预算。格式检查不能替代人工或平台验收。
