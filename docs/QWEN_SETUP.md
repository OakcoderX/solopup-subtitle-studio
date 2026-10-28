# Qwen setup / Qwen 申请与配置

[English](QWEN_SETUP.en.md) · [完整中文](QWEN_SETUP.zh-CN.md)

# Qwen：申请、测试，再准备批量制作

[English](QWEN_SETUP.en.md) · [中文](QWEN_SETUP.zh-CN.md)

云端 AI 制作需要自己的 Qwen／百炼 API Key 与模型权限。没有 Key，仍可离线导入已有字幕并人工校对。

## 1. 申请自己的 Key

1. 登录阿里云，按控制台要求开通百炼 Model Studio；协议、身份认证及账号要求由本人完成。
2. 在所选地域创建 API Key。Key、接口地址与有权限的模型 Code 必须匹配同一地域，不把聊天网页、OAuth 或编程套餐凭证当作通用模型 API Key。
3. 打开 SoloPup“AI接口设置／Qwen设置”，自己输入 Key、对应的 HTTPS 地址和模型 Code，不发到聊天、Issue 或命令参数中。
4. 保存只写本机配置，不调用模型、不测试权限，也不验证计费。Key 在本地保存，并在支持的系统上设置仅所有者可读写权限，不进入浏览器存储、Git 或发布包。

[官方 API Key 申请说明](https://help.aliyun.com/zh/model-studio/get-api-key/)

## 2. 先查试用额度，再测试小片段

通常同一个 API Key 先消耗适用试用额度，之后按账号计费继续使用，不需要向 SoloPup 另买“收费 Key”。先在服务商控制台核对具体模型／版本、地域、剩余额度及到期日。

2026-10-28 核对的官方说明为：新人额度适用于指定北京地域模型，通常有 90 天有效期，各模型／快照额度独立。优惠与规则可能变化，其他地域／账号可能不同或没有试用额度；不保证每个配置模型或完整一季都能免费运行。

如模型支持，先在百炼开启“免费额度用完即停”，等待生效后评估。SoloPup 不替你设置，也无法验证这项保护。没有适用免费额度时，先自行决定是否使用付费能力，再调用模型。

先用一段 30—60 秒真实对白，检查转写、翻译、断句和读速，再扩大制作。无对白合成示例不能评估识别质量。主动发起的试用调用可能消耗额度或产生费用；首次启动和保存配置不会暗中测试。

[官方免费额度与计费说明](https://help.aliyun.com/zh/model-studio/new-free-quota)

## 3. 为批量制作准备计费与预算

效果可用后，在百炼完成账号要求、准备余额／支付方式，核对模型权限、计费方式、调用限额及费用预警。试用额度耗尽后仍需持续制作时，按服务商说明开通适当的付费能力，并自行决定是否关闭“用完即停”。通常原 Key 可以继续使用，费用由模型服务商收取。

SoloPup 每批支持一至五集，后台队列使用现有实时请求，并不是服务商名为 Batch API 的产品，不套用该产品的折扣或试用规则。长音频、复核、翻译及重试都会增加用量，先根据小样消耗估算预算，再逐步扩大批次。

## SoloPup 检查什么？

需要云模型的新任务未配置 Key 时，会在入队前被拦截。已配置不等于有效、免费、有余额、已付费可用或模型兼容；这些仍需在服务商控制台确认。额度或权限失败时先检查原任务状态，再决定是否重提，避免无谓的重复调用。

[先试离线校对](QUICKSTART.zh-CN.md) · [隐私与限制](FAQ.zh-CN.md)


---

# Qwen: apply, evaluate, then prepare batch work

[English](QWEN_SETUP.en.md) · [中文](QWEN_SETUP.zh-CN.md)

Cloud AI production needs your own Qwen/Model Studio API key and model access. Imported-subtitle review remains available offline without a key.

## 1. Create your own key

1. Sign in to Alibaba Cloud and activate Model Studio as required. Complete agreements, identity checks and account requirements yourself.
2. Create an API key in the intended region. The key, endpoint and accessible model IDs must match that region. Chat website, OAuth and coding-plan credentials are not general model API keys.
3. Open AI接口设置 / Qwen设置 in SoloPup. Enter the secret yourself, with the matching HTTPS endpoint and model codes. Keep it out of chat, issues and command arguments.
4. Saving only writes local configuration. It does not make a model request, test permissions or verify billing. The secret is stored locally with owner-only permissions where supported, not in browser storage, Git or release files.

[Official API key instructions](https://help.aliyun.com/en/model-studio/get-api-key)

## 2. Check trial quota, then evaluate a short clip

Usually the same API key first consumes applicable trial quota and later continues under account billing. There is no separate “paid key” you must buy from SoloPup. Check the exact model/version, region, remaining quota and expiration in the provider console.

The official guidance checked on 2026-10-28 described eligible new-user quotas for designated Beijing-region models, generally valid for 90 days, with independent quotas per model/snapshot. Offers and rules can change. Other regions/accounts may have different or no trial quota; neither every configured model nor a whole season is guaranteed free.

Where supported, enable the provider’s Free Quota Only protection and wait for it to take effect before evaluation. SoloPup neither configures nor verifies this protection. If there is no applicable free quota, decide whether to use paid access before invoking the model.

Use one 30–60 second clip with real dialogue. Check transcription, translation, screen breaks and reading speed before expanding. The silent synthetic demo is not a recognition-quality test. A user-initiated trial call can consume quota or incur charges; startup and saving never silently issue a test call.

[Official trial quota and billing rules](https://help.aliyun.com/en/model-studio/new-free-quota)

## 3. Prepare billing and budget for batch production

Once the result is useful, complete account requirements, prepare funds/payment, and verify model permissions, billing, rate limits and cost alerts in Model Studio. To continue after trial quota runs out, enable the appropriate paid access according to the provider instructions and decide whether to disable Free Quota Only. Usually the original key continues to work; provider fees are charged by the provider.

SoloPup’s queue accepts one to five episodes per batch using its existing real-time requests. It is not the provider product named Batch API, so do not assume that product’s discounts or trial rules apply. Long audio, review, translation and retries add usage. Estimate costs from a small sample and expand gradually.

## What SoloPup checks

Cloud jobs without a configured key are rejected before queueing. Key presence does not verify validity, free quota, balance, paid access or model compatibility. Check these in the provider console. On access/quota failures, inspect the original task state before resubmitting to avoid unnecessary duplicate calls.

[Start with offline review](QUICKSTART.md) · [Privacy and limitations](FAQ.md)
