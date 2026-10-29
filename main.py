"""
爱弥斯 · 语音插件（AstrBot）

能力：
    /voice <文字>                管理员立即合成一条语音
    语音 你好呀 / 朗读 晚安 等    自然语言触发（配置 prefixes）
    概率语音回复                  普通回复按 probability 改成语音

注意：
    AstrBot 的 Comp.Record 目前只接受 wav，因此默认用 CosyVoice 的 wav 输出。
    若开启流式输出，概率语音可能来不及替换，建议关闭该会话的流式。
"""
import random
import re
import sys
import time
from pathlib import Path

import astrbot.api.message_components as Comp
from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star

sys.path.insert(0, str(Path(__file__).resolve().parent))
from aemeath_voice_core.breezeblue import BreezeBlue  # noqa: E402
from aemeath_voice_core.cosyvoice import CosyVoice  # noqa: E402

try:
    from astrbot.core.utils.astrbot_path import get_astrbot_data_path
except Exception:  # 旧版本 AstrBot 兜底
    def get_astrbot_data_path():
        return "data"

SEP = " 　:：,，.。!！~～\"“”'‘’"


class AemeathVoicePlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        self._last: dict[str, float] = {}
        logger.info("[aemeath_voice] 语音插件已加载（BreezeBlue 优先，可回退 CosyVoice）")

    # ---------- 工具 ----------

    def _data_dir(self) -> Path:
        path = Path(get_astrbot_data_path()) / "plugin_data" / "astrbot_plugin_aemeath_voice"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _cosyvoice_client(self) -> CosyVoice:
        return CosyVoice(
            api_key=self.config.get("api_key", ""),
            voice=self.config.get("voice", ""),
            model=self.config.get("model", "cosyvoice-v3.5-flash"),
            url=self.config.get(
                "ws_url",
                "wss://maas.qianwenaiapi.com/api-ws/v1/inference",
            ),
            fmt=self.config.get("format", "wav"),
            sample_rate=int(self.config.get("sample_rate", 22050)),
            instruction=self.config.get("instruction", ""),
        )

    def _breezeblue_client(self) -> BreezeBlue:
        return BreezeBlue(
            api_key=self.config.get("breezeblue_api_key", ""),
            voice=self.config.get("breezeblue_voice_id", "voc_s7q9c9v958re"),
            model=self.config.get("breezeblue_model", "breeze-tts-2"),
            url=self.config.get("breezeblue_url", "https://api.breeze.blue"),
            language=self.config.get("breezeblue_language", "zh"),
            instruction=self.config.get(
                "breezeblue_instruction",
                "用爱弥斯那种温柔、自然、像在 QQ 里随口聊天的语气说，不要客服腔。",
            ),
            guidance_scale=float(self.config.get("breezeblue_guidance_scale", 4.0)),
            fmt="wav",
        )

    def _match_prefix(self, text: str) -> str | None:
        prefixes = sorted(self.config.get("prefixes", []), key=len, reverse=True)
        for prefix in prefixes:
            if not prefix or not text.startswith(prefix):
                continue
            rest = text[len(prefix):]
            lead = rest.lstrip(SEP)
            if len(lead) < len(rest):
                return lead.strip() or None
            if len(prefix) >= 2:
                return rest.strip() or None
        return None

    def _cooling(self, key: str, seconds: int) -> bool:
        now = time.time()
        if now - self._last.get(key, 0.0) < seconds:
            return True
        self._last[key] = now
        return False

    async def _synth_file(self, text: str) -> Path:
        timeout = float(self.config.get("timeout", 60))
        primary = str(self.config.get("provider", "breezeblue")).lower()
        breeze_on = bool(self.config.get("breezeblue_enabled", True))
        cosy_on = bool(self.config.get("cosyvoice_enabled", True))

        if primary == "cosyvoice" and cosy_on:
            providers = ["cosyvoice"]
        elif primary == "breezeblue" and breeze_on:
            providers = ["breezeblue"]
        elif breeze_on:
            providers = ["breezeblue"]
        elif cosy_on:
            providers = ["cosyvoice"]
        else:
            raise RuntimeError("BreezeBlue 和 CosyVoice 都已被手动关闭")

        if (
            self.config.get("fallback_to_cosyvoice", True)
            and cosy_on
            and "cosyvoice" not in providers
        ):
            providers.append("cosyvoice")

        errors: list[str] = []
        for provider in providers:
            try:
                if provider == "breezeblue":
                    audio = await self._breezeblue_client().synthesize(text, timeout=timeout)
                    suffix = "wav"
                else:
                    audio = await self._cosyvoice_client().synthesize(text, timeout=timeout)
                    suffix = str(self.config.get("format", "wav"))
                if not audio:
                    raise RuntimeError("返回空音频")
                path = self._data_dir() / f"voice_{time.time_ns()}.{suffix}"
                path.write_bytes(audio)
                self._cleanup()
                logger.info("[aemeath_voice] 合成后端: %s", provider)
                return path
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{provider}: {exc}")
                logger.warning("[aemeath_voice] %s 合成失败，尝试下一个后端: %s", provider, exc)
        raise RuntimeError("所有语音后端都失败：" + " | ".join(errors))

    def _cleanup(self) -> None:
        """清理 1 小时前的临时语音"""
        cutoff = time.time() - 3600
        for f in self._data_dir().glob("voice_*"):
            try:
                if f.stat().st_mtime < cutoff:
                    f.unlink(missing_ok=True)
            except OSError:
                pass

    @staticmethod
    def _strip_markers(text: str) -> str:
        return re.sub(r"\[(?:emoji|表情|图片)[^\]]*\]", "", text, flags=re.IGNORECASE).strip()

    # ---------- 指令 ----------

    @filter.command("voice")
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def voice_cmd(self, event: AstrMessageEvent):
        """立即发送一条语音：/voice 你好呀"""
        args = (event.message_str or "").strip().split(maxsplit=1)
        text = args[1].strip() if len(args) > 1 else ""
        if not text:
            yield event.plain_result("用法: /voice <文字>")
            return
        try:
            path = await self._synth_file(text)
        except Exception as exc:  # noqa: BLE001
            logger.error("[aemeath_voice] 合成失败: %s", exc)
            yield event.plain_result("语音合成失败，请检查 API Key 与音色配置")
            return
        yield event.chain_result([Comp.Record(file=str(path), url=str(path))])

    # ---------- 自然语言触发 ----------

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def voice_trigger(self, event: AstrMessageEvent):
        """语音 xxx / 朗读 xxx / 说 你好 等前缀触发"""
        if not self.config.get("enabled", True):
            return
        text = (event.message_str or "").strip()
        content = self._match_prefix(text)
        if not content:
            return

        event.stop_event()
        if self._cooling(event.unified_msg_origin, int(self.config.get("cooldown", 10))):
            yield event.plain_result("刚说过啦，歇一下嘛～")
            return

        try:
            path = await self._synth_file(content)
        except Exception as exc:  # noqa: BLE001
            logger.error("[aemeath_voice] 触发合成失败: %s", exc)
            yield event.plain_result("语音合成失败，稍后再试～")
            return

        event._aemeath_voice_sent = True  # 标记，概率语音钩子跳过
        yield event.chain_result([Comp.Record(file=str(path), url=str(path))])

    # ---------- 概率语音 ----------

    @filter.on_decorating_result()
    async def maybe_voice_reply(self, event: AstrMessageEvent):
        """普通 AI 回复按概率改成语音（版本依赖钩子，失败只记日志）"""
        if not self.config.get("enabled", True):
            return
        if getattr(event, "_aemeath_voice_sent", False):
            return
        prob = float(self.config.get("probability", 0.0))
        if prob <= 0 or random.random() >= prob:
            return

        try:
            result = event.get_result()
            if result is None:
                return
            chain = getattr(result, "chain", [])
            texts = [seg.text for seg in chain if isinstance(seg, Comp.Plain)]
            raw = "".join(texts)

            # 插件进度/状态提示（正在生成、请稍候等）不转语音
            if re.search(
                r"正在(生成|准备|处理|加载|下载|转码|查询|搜索)|请稍候|处理中|生成中|准备中|稍等",
                raw,
            ):
                return
            # 含链接的回复不转语音（点歌分享、卡片链接等，避免把 URL 念出来）
            if re.search(r"https?://", raw):
                return

            text = self._strip_markers(raw)
            if not text or len(text) > int(self.config.get("max_chars", 120)):
                return
            # 表情图片可以存在，但语音命中时会丢弃图片：
            # QQ 不支持语音和表情包在同一条消息里，二者只保留语音。
            rich = [
                seg
                for seg in chain
                if not isinstance(seg, (Comp.Plain, Comp.Reply, Comp.Image))
            ]
            if rich or len([seg for seg in chain if isinstance(seg, Comp.Plain)]) != len(texts):
                return
            if self._cooling(event.unified_msg_origin, int(self.config.get("cooldown", 10))):
                return

            path = await self._synth_file(text)
            kept = [seg for seg in chain if isinstance(seg, Comp.Reply)]
            result.chain = kept + [Comp.Record(file=str(path), url=str(path))]
            logger.info("[aemeath_voice] 概率语音命中（丢弃表情）: %s", text[:40])
        except Exception as exc:  # noqa: BLE001
            logger.warning("[aemeath_voice] 概率语音失败（不影响文字回复）: %s", exc)
