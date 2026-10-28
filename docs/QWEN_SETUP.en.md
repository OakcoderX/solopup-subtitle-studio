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
