"""BreezeBlue TTS HTTP 客户端（AstrBot 语音插件）"""
import aiohttp


class BreezeBlue:
    def __init__(
        self,
        api_key: str,
        voice: str,
        model: str = "breeze-tts-2",
        url: str = "https://api.breeze.blue",
        language: str = "zh",
        instruction: str = "",
        guidance_scale: float = 4.0,
        fmt: str = "wav",
    ):
        self.api_key = api_key
        self.voice = voice
        self.model = model
        self.url = url.rstrip("/")
        self.language = language
        self.instruction = (instruction or "").strip()
        self.guidance_scale = float(guidance_scale)
        self.fmt = fmt

    async def synthesize(self, text: str, timeout: float = 60) -> bytes:
        if not self.api_key:
            raise RuntimeError("BreezeBlue API Key 未配置")
        if not self.voice:
            raise RuntimeError("BreezeBlue voice_id 未配置")
        if not text.strip():
            raise ValueError("文本为空")

        payload = {
            "text": text,
            "model_id": self.model,
            "language_code": self.language,
            "voice_settings": {"guidance_scale": self.guidance_scale},
        }
        if self.instruction:
            payload["instructions"] = self.instruction

        endpoint = f"{self.url}/v1/text-to-speech/{self.voice}"
        headers = {
            "xi-api-key": self.api_key,
            "Content-Type": "application/json",
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(
                endpoint,
                params={"output_format": self.fmt},
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=timeout),
            ) as resp:
                if resp.status != 200:
                    body = (await resp.text())[:300]
                    raise RuntimeError(f"BreezeBlue HTTP {resp.status}: {body}")
                audio = await resp.read()
        if not audio:
            raise RuntimeError("BreezeBlue 未返回音频")
        return audio
