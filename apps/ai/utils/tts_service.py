"""
本地文本转语音服务。

优先使用系统服务配置里的高质量 TTS；未配置时才使用服务器本机 SAPI 兜底。
"""

import base64
import json
import os
import platform
import subprocess
import tempfile
from html import escape
from pathlib import Path
from typing import Any, Dict, List, Optional


class TTSError(Exception):
    """文本转语音服务异常"""


class LocalTTSService:
    """本地文本转语音服务"""

    MAX_TEXT_LENGTH = 600
    STYLE_PRESETS = {
        "natural": {"rate": "-8%", "pitch": "+2%", "volume": "92", "pause": "220ms"},
        "calm": {"rate": "-14%", "pitch": "+0%", "volume": "90", "pause": "280ms"},
        "crisp": {"rate": "-4%", "pitch": "+3%", "volume": "94", "pause": "170ms"},
    }

    def synthesize_wav(
        self,
        text: str,
        voice_name: Optional[str] = None,
        voice_style: str = "natural",
    ) -> bytes:
        content = self._normalize_text(text)
        if not content:
            raise TTSError("播报内容不能为空")

        edge_audio = self._synthesize_edge_tts(content, voice_name, voice_style)
        if edge_audio:
            return edge_audio

        configured_audio = self._try_configured_tts(content, voice_name, voice_style)
        if configured_audio:
            return configured_audio

        return self._synthesize_windows_sapi(content, voice_name, voice_style)

    def list_voices(self) -> List[Dict[str, str]]:
        edge_voices = self._list_edge_tts_voices()
        if edge_voices:
            return edge_voices

        configured = self._get_enabled_tts_config()
        if configured:
            extra = self._parse_extra_config(configured)
            voices = extra.get("voices")
            if isinstance(voices, list):
                return [
                    {
                        "name": str(item.get("name") or item.get("voice") or ""),
                        "culture": str(item.get("culture") or item.get("lang") or "zh-CN"),
                        "gender": str(item.get("gender") or ""),
                        "age": "Neural",
                        "source": "configured",
                    }
                    for item in voices
                    if isinstance(item, dict)
                ]
            default_voice = extra.get("voice") or self._default_voice_for_provider(configured.provider)
            return [{
                "name": default_voice,
                "culture": extra.get("lang") or "zh-CN",
                "gender": "",
                "age": "Neural",
                "source": configured.get_provider_display(),
            }]

        if platform.system().lower() != "windows":
            return []

        script = r"""
param([string]$OutputPath)
Add-Type -AssemblyName System.Speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
$voices = @()
foreach ($voice in $synth.GetInstalledVoices()) {
    if ($voice.Enabled) {
        $voices += [PSCustomObject]@{
            name = $voice.VoiceInfo.Name
            culture = $voice.VoiceInfo.Culture.Name
            gender = [string]$voice.VoiceInfo.Gender
            age = [string]$voice.VoiceInfo.Age
        }
    }
}
$voices | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $OutputPath -Encoding UTF8
$synth.Dispose()
"""

        with tempfile.TemporaryDirectory(prefix="dtcall_tts_") as temp_dir:
            output_path = os.path.join(temp_dir, "voices.json")
            self._run_powershell(script, ["-OutputPath", output_path])
            if not os.path.exists(output_path):
                return []

            import json

            raw = Path(output_path).read_text(encoding="utf-8-sig").strip()
            if not raw:
                return []
            data = json.loads(raw)
            if isinstance(data, dict):
                data = [data]
            return data if isinstance(data, list) else []

    def _normalize_text(self, text: str) -> str:
        content = " ".join(str(text or "").split())
        content = content.replace("DTCALL", "D T Call").replace("DTCall", "D T Call")
        content = content.replace("AI", "A I")
        return content[: self.MAX_TEXT_LENGTH]

    def _get_enabled_tts_config(self):
        try:
            from apps.system.models import ServiceCategory, ServiceConfiguration

            return (
                ServiceConfiguration.objects.filter(
                    category=ServiceCategory.TTS,
                    is_enabled=True,
                )
                .exclude(base_url="")
                .order_by("-status", "-updated_at")
                .first()
            )
        except Exception:
            return None

    def _parse_extra_config(self, config) -> Dict[str, Any]:
        raw = getattr(config, "extra_config", "") or "{}"
        try:
            data = json.loads(raw)
            return data if isinstance(data, dict) else {}
        except (TypeError, ValueError):
            return {}

    def _try_configured_tts(
        self,
        text: str,
        voice_name: Optional[str],
        voice_style: str,
    ) -> Optional[bytes]:
        config = self._get_enabled_tts_config()
        if not config:
            return None

        try:
            provider = (config.provider or "").lower()
            if provider == "azure":
                return self._synthesize_azure_tts(config, text, voice_name, voice_style)
            return self._synthesize_http_tts(config, text, voice_name, voice_style)
        except Exception as exc:
            # 不让高质量服务的短暂故障影响主流程，回退到本机兜底。
            import logging

            logging.getLogger(__name__).warning("配置TTS服务失败，回退本机语音: %s", exc)
            return None

    def _default_voice_for_provider(self, provider: str) -> str:
        provider = (provider or "").lower()
        if provider == "azure":
            return "zh-CN-XiaoxiaoNeural"
        if provider == "aliyun":
            return "longxiaochun"
        if provider == "tencent":
            return "101001"
        if provider == "baidu":
            return "5003"
        return "zh-CN-XiaoxiaoNeural"

    def _build_azure_ssml(self, text: str, voice: str, voice_style: str) -> str:
        style = self.STYLE_PRESETS.get(voice_style) or self.STYLE_PRESETS["natural"]
        return (
            '<speak version="1.0" xml:lang="zh-CN" '
            'xmlns="http://www.w3.org/2001/10/synthesis" '
            'xmlns:mstts="https://www.w3.org/2001/mstts">'
            f'<voice name="{escape(voice, quote=True)}">'
            f'<prosody rate="{style["rate"]}" pitch="{style["pitch"]}">'
            f"{escape(text, quote=True)}"
            "</prosody>"
            "</voice>"
            "</speak>"
        )

    def _synthesize_azure_tts(
        self,
        config,
        text: str,
        voice_name: Optional[str],
        voice_style: str,
    ) -> bytes:
        import requests

        extra = self._parse_extra_config(config)
        base_url = (config.base_url or "").rstrip("/")
        endpoint = extra.get("endpoint") or base_url
        if not endpoint.endswith("/cognitiveservices/v1"):
            endpoint = f"{endpoint}/cognitiveservices/v1"

        voice = voice_name or extra.get("voice") or "zh-CN-XiaoxiaoNeural"
        response = requests.post(
            endpoint,
            data=self._build_azure_ssml(text, voice, voice_style).encode("utf-8"),
            headers={
                "Ocp-Apim-Subscription-Key": config.api_key,
                "Content-Type": "application/ssml+xml",
                "X-Microsoft-OutputFormat": extra.get(
                    "output_format", "riff-24khz-16bit-mono-pcm"
                ),
                "User-Agent": "dtcall-tts",
            },
            timeout=int(extra.get("timeout", 20)),
        )
        if response.status_code >= 400:
            raise TTSError(f"Azure TTS调用失败: {response.status_code}")
        return response.content

    def _synthesize_http_tts(
        self,
        config,
        text: str,
        voice_name: Optional[str],
        voice_style: str,
    ) -> bytes:
        import requests

        extra = self._parse_extra_config(config)
        voice = voice_name or extra.get("voice") or self._default_voice_for_provider(config.provider)
        headers = extra.get("headers") if isinstance(extra.get("headers"), dict) else {}
        headers = {
            "Authorization": f"Bearer {config.api_key}" if config.api_key else "",
            **headers,
        }
        headers = {key: value for key, value in headers.items() if value}
        payload = {
            extra.get("text_field", "text"): text,
            extra.get("voice_field", "voice"): voice,
            extra.get("style_field", "style"): voice_style,
        }
        if extra.get("model"):
            payload[extra.get("model_field", "model")] = extra["model"]

        response = requests.post(
            config.base_url,
            json=payload,
            headers=headers,
            timeout=int(extra.get("timeout", 30)),
        )
        if response.status_code >= 400:
            raise TTSError(f"TTS服务调用失败: {response.status_code}")

        content_type = response.headers.get("Content-Type", "").lower()
        if content_type.startswith("audio/") or response.content[:4] == b"RIFF":
            return response.content

        data = response.json()
        audio_base64 = data.get(extra.get("audio_base64_field", "audio_base64"))
        if audio_base64:
            return base64.b64decode(audio_base64)
        audio_url = data.get(extra.get("audio_url_field", "audio_url"))
        if audio_url:
            audio_response = requests.get(audio_url, timeout=int(extra.get("timeout", 30)))
            if audio_response.status_code >= 400:
                raise TTSError(f"TTS音频下载失败: {audio_response.status_code}")
            return audio_response.content
        raise TTSError("TTS服务未返回音频内容")

    def _build_ssml(self, text: str, voice_style: str) -> str:
        style = self.STYLE_PRESETS.get(voice_style) or self.STYLE_PRESETS["natural"]
        escaped = escape(text, quote=True)
        for mark in ["。", "！", "？", "；", "!", "?", ";"]:
            escaped = escaped.replace(mark, f'{mark}<break time="{style["pause"]}"/>')
        escaped = escaped.replace("，", '，<break time="110ms"/>')
        escaped = escaped.replace(",", ',<break time="90ms"/>')
        return (
            '<speak version="1.0" xml:lang="zh-CN">'
            f'<prosody rate="{style["rate"]}" pitch="{style["pitch"]}" volume="{style["volume"]}">'
            f"{escaped}"
            "</prosody>"
            "</speak>"
        )

    def _list_edge_tts_voices(self):
        """列出 Edge TTS 可用中文音色"""
        try:
            import asyncio
            import edge_tts

            async def _list():
                voices = await edge_tts.VoicesManager.create()
                return [
                    {
                        "name": v["ShortName"],
                        "culture": v["Locale"],
                        "gender": v.get("Gender", ""),
                        "age": "Neural",
                        "friendly": v.get("FriendlyName", v["ShortName"]),
                    }
                    for v in voices.voices
                    if v["Locale"].startswith("zh")
                ]

            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(_list())
            finally:
                loop.close()
        except Exception:
            return []

    def _synthesize_edge_tts(
        self,
        text: str,
        voice_name: Optional[str],
        voice_style: str,
    ) -> Optional[bytes]:
        """使用 Microsoft Edge TTS（免费神经网络语音，需要 edge-tts 库）"""
        try:
            import asyncio
            import edge_tts
            from edge_tts import Communicate

            voice = voice_name or "zh-CN-XiaoxiaoNeural"
            rate = {
                "natural": "-8%", "calm": "-14%", "crisp": "-4%"
            }.get(voice_style, "-8%")

            async def _generate():
                communicate = Communicate(text, voice, rate=rate)
                chunks = []
                async for chunk in communicate.stream():
                    if chunk["type"] == "audio":
                        chunks.append(chunk["data"])
                return b"".join(chunks)

            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(_generate())
            finally:
                loop.close()
        except ImportError:
            return None
        except Exception:
            return None

    def _synthesize_windows_sapi(
        self,
        text: str,
        voice_name: Optional[str],
        voice_style: str,
    ) -> bytes:
        if platform.system().lower() != "windows":
            raise TTSError("当前服务器暂未配置高质量文本转语音服务")

        script = r"""
param([string]$TextPath, [string]$SsmlPath, [string]$OutputPath, [string]$VoiceName)
Add-Type -AssemblyName System.Speech
$text = Get-Content -LiteralPath $TextPath -Raw -Encoding UTF8
$ssml = Get-Content -LiteralPath $SsmlPath -Raw -Encoding UTF8
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
$synth.Volume = 92
$synth.Rate = -2
$voices = $synth.GetInstalledVoices() | Where-Object { $_.Enabled }
if ($VoiceName) {
    $matched = $voices | Where-Object { $_.VoiceInfo.Name -eq $VoiceName } | Select-Object -First 1
    if ($matched) { $synth.SelectVoice($matched.VoiceInfo.Name) }
} else {
    $ranked = foreach ($voice in $voices) {
        $name = $voice.VoiceInfo.Name
        $culture = $voice.VoiceInfo.Culture.Name
        $score = 0
        if ($culture -like 'zh*') { $score += 100 }
        if ($name -match 'Xiaoxiao|Xiaoyi|Yunxi|Yunjian') { $score += 80 }
        if ($name -match 'Huihui|Yaoyao|Kangkang') { $score += 55 }
        if ($name -match 'Chinese|Mandarin|中文|普通话') { $score += 45 }
        if ($name -match 'Desktop|Legacy|Compact|eSpeak') { $score -= 40 }
        [PSCustomObject]@{ Voice = $voice; Score = $score }
    }
    $preferred = $ranked | Sort-Object Score -Descending | Select-Object -First 1
    if ($preferred -and $preferred.Score -gt 0) { $synth.SelectVoice($preferred.Voice.VoiceInfo.Name) }
}
$synth.SetOutputToWaveFile($OutputPath)
try {
    $synth.SpeakSsml($ssml)
} catch {
    $synth.Speak($text)
}
$synth.Dispose()
"""

        with tempfile.TemporaryDirectory(prefix="dtcall_tts_") as temp_dir:
            text_path = os.path.join(temp_dir, "speech.txt")
            ssml_path = os.path.join(temp_dir, "speech.ssml")
            wav_path = os.path.join(temp_dir, "speech.wav")
            Path(text_path).write_text(text, encoding="utf-8")
            Path(ssml_path).write_text(self._build_ssml(text, voice_style), encoding="utf-8")
            self._run_powershell(
                script,
                [
                    "-TextPath",
                    text_path,
                    "-SsmlPath",
                    ssml_path,
                    "-OutputPath",
                    wav_path,
                    "-VoiceName",
                    voice_name or "",
                ],
            )

            if not os.path.exists(wav_path) or os.path.getsize(wav_path) <= 44:
                raise TTSError("本地语音合成失败，请检查服务器是否安装中文语音")

            return Path(wav_path).read_bytes()

    def _run_powershell(self, script: str, args: List[str]) -> None:
        with tempfile.NamedTemporaryFile(
            "w", suffix=".ps1", encoding="utf-8", delete=False
        ) as script_file:
            script_path = script_file.name
            script_file.write(script)

        try:
            completed = subprocess.run(
                [
                    "powershell.exe",
                    "-NoProfile",
                    "-NonInteractive",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    script_path,
                    *args,
                ],
                capture_output=True,
                text=True,
                timeout=20,
                check=False,
            )
            if completed.returncode != 0:
                message = (completed.stderr or completed.stdout or "").strip()
                raise TTSError(message or "本地语音服务调用失败")
        finally:
            try:
                os.remove(script_path)
            except OSError:
                pass
