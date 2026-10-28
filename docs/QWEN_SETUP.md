# Qwen setup 从试用评估到批量制作

SoloPup Subtitle Studio的云端AI识别、翻译和复核需要使用者自己的Qwen API Key。没有可用Key与模型权限，不能完成这些AI制作任务；已有字幕的导入、播放和人工校对仍能离线使用。

本说明于2026-10-28核对阿里云百炼官方文档。优惠、地域、模型和计费条件可能更新；以你的控制台为准。软件不发放Key、不赠送额度，也不会替你开通收费。

## 1 申请自己的Key

1. 注册/登录阿里云，按控制台要求开通百炼Model Studio。协议、身份认证等由你本人完成。
2. 在官方API Key页面选择地域并创建Key。Key、接口地址和模型必须匹配同一地域及实际模型权限；不要把聊天网页、OAuth或编程套餐的凭证当作通用模型API Key。
3. 打开SoloPup“AI接口设置/Qwen设置”，自己粘贴Key，填写该地域接口地址和模型Code。Key只保存到本机，不进入浏览器存储或发布文件。不要把它发到聊天、工单或GitHub。
4. 点击保存只写配置，不调用模型、不验证权限，也不产生用于测试的API请求。

[官方API Key申请步骤](https://help.aliyun.com/zh/model-studio/get-api-key/)

## 2 先检查试用额度 再测试小片段

通常是同一个API Key先消耗适用免费额度，之后按账号计费设置继续使用，并不存在必须另买的“收费Key”。

先在百炼查看**本次使用的具体模型/版本、地域、剩余额度和到期日**。官方当前说明：新人额度仅适用于指定北京地域模型，通常有90天有效期，不同模型/快照额度独立；不能保证本软件填写的每个模型都有免费试用。海外账号/地域须以对应官方控制台规则为准，不承诺同样优惠。

如模型支持，先在百炼开启“免费额度用完即停”，等待设置生效，避免评估时超出额度继续计费。该保护由服务商控制，SoloPup不会替你设置，也无法验证是否已生效。没有可用免费额度时，请先决定是否按量付费，不能把一次测试叫作“保证免费”。

选30—60秒带真实对白的小片段，只测试一段，检查识别、翻译、断句和读速，再决定是否继续。不要用无对白的合成示例判断识别质量。测试是你主动发起的模型调用，可能消耗额度或产生费用；软件不会在保存Key或首次启动时暗中测试。

[官方免费额度、有效期与用完即停](https://help.aliyun.com/zh/model-studio/new-free-quota)

## 3 正式批量前准备计费与预算

确认效果后，在百炼按账号要求完成认证、准备余额/支付方式，确认模型权限、计费方式、调用限额和费用预警。若要在试用额度耗尽后持续运行，需按官方说明启用适当的按量付费能力并自行决定是否关闭“用完即停”。通常原Key可以继续使用，不需要向SoloPup购买Key。账号实际费用由模型服务商收取。

软件的“每批1—5集后台队列”使用现有模型实时请求，不等同百炼名为Batch的API产品。不要套用Batch产品的优惠或免费规则。免费额度覆盖不等于能够免费跑完整季；长音频、复核、翻译与重试都会增加调用量。先根据小样消耗准备预算，再逐步扩大批次。

系统会在需要云模型的新任务入队前检查是否配置Key；但有Key不等于有效、免费或已付费可用，真实额度/余额/权限仍需在百炼确认。额度或权限失败时先处理原任务状态，不盲目重复提交。

## English quick guide

Cloud AI production requires your own Qwen/Model Studio API key. Local imported-subtitle review remains available without one.

Create a key in the provider console, then configure the matching region, endpoint and accessible model IDs in SoloPup. Keep the secret local. Saving makes no model call and does not verify access.

Check the exact model's trial eligibility, remaining quota and expiry. Where eligible, enable the provider's Free Quota Only protection before evaluating a 30–60 second dialogue clip. Trial availability varies; no free run is guaranteed. A trial invocation can consume quota or be billed.

Before regular batch work, verify the result, account requirements, funds, billing, rate limits and budget alerts. Usually the same API key continues under pay-as-you-go billing; there is no separate key to purchase from this app. SoloPup's episode queue is not the provider's Batch API product. The app checks key presence before cloud jobs, not actual billing readiness or free-quota balance.

[Official key setup](https://help.aliyun.com/en/model-studio/get-api-key) · [Official trial/billing rules](https://help.aliyun.com/en/model-studio/new-free-quota)
