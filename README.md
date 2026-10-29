# 爱弥斯·语音

AstrBot 语音插件：**BreezeBlue 优先，失败/额度不足自动回退 CosyVoice**。

## 功能

- `/voice <文字>`：管理员立即合成一条语音
- 自然语言前缀：`语音 你好呀`、`朗读 晚安`、`说 想你`
- 概率语音：普通 AI 回复按概率替换成语音
- 双后端：
  - BreezeBlue：情绪/语气更自然，支持 `instructions`
  - CosyVoice：BreezeBlue 失败时自动兜底

## 配置

在 AstrBot 插件配置里填写：

```text
provider = breezeblue
fallback_to_cosyvoice = true
cosyvoice_enabled = true   # 手动关闭 CosyVoice 时设为 false

breezeblue_api_key = 你的 BreezeBlue Key
breezeblue_voice_id = voc_xxx
breezeblue_model = breeze-tts-2
breezeblue_language = zh
breezeblue_instruction = 用爱弥斯温柔、自然的语气说...
breezeblue_guidance_scale = 4.0

api_key = 你的 CosyVoice/千问 Key
voice = 你的 CosyVoice 音色 ID
model = cosyvoice-v3.5-plus
ws_url = wss://maas.qianwenaiapi.com/api-ws/v1/inference
```

**API Key 只放在 AstrBot 本地配置中，不要提交到 GitHub。**

## 行为

```text
BreezeBlue 合成功 → 直接发送
BreezeBlue 失败 → 日志记录 → CosyVoice 再试
两者都失败 → 回复文字错误提示
```

语音命中时会丢弃表情图，只发语音，因为 QQ 不支持语音和表情包同条发送。

## 安装

放入：

```text
AstrBot/data/plugins/astrbot_plugin_aemeath_voice
```

依赖：

```text
aiohttp
```

## 说明

- `Comp.Record` 稳定支持 WAV，因此 BreezeBlue 固定请求 `output_format=wav`。
- BreezeBlue 的 `instructions` 支持生气、平淡、开心、委屈等自然语言表演指令。
- 这个插件只负责“说话”，不负责唱歌；唱歌请用独立的点唱插件。
