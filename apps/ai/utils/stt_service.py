"""
语音转文字服务模块
提供语音文件转文字功能，支持多种语音转文字服务
"""

import os
import logging
import json
from typing import Optional, Dict, Any
import requests

logger = logging.getLogger(__name__)


def get_stt_config_from_db():
    """从数据库获取语音转文字配置"""
    try:
        from apps.ai.models import AIModelConfig
        active_configs = AIModelConfig.get_active_runtime_configs()
        for config in active_configs:
            provider = config.get('provider')
            if provider in ['openai', 'alibaba', 'deepseek', 'doubao', 'tencent', 'azure']:
                if provider in ['alibaba', 'deepseek', 'doubao', 'tencent']:
                    provider = 'openai'
                model_name = config.get('model_name') or ''
                if config.get('model_type') != 'audio' and 'whisper' not in model_name.lower():
                    model_name = 'whisper-1'
                return {
                    'service_type': provider,
                    'api_key': config.get('api_key'),
                    'base_url': config.get('api_base') or config.get('base_url'),
                    'model': model_name or 'whisper-1'
                }
    except Exception as e:
        logger.warning(f"从数据库获取AI配置失败: {str(e)}")

    return None


def get_configured_stt_service():
    """从系统服务配置中获取已启用的语音转文字服务"""
    try:
        from apps.system.models import ServiceCategory, ServiceConfiguration
        config = (
            ServiceConfiguration.objects.filter(
                category=ServiceCategory.STT,
                is_enabled=True,
            )
            .exclude(api_key='')
            .order_by('-updated_at', '-created_at')
            .first()
        )
        if not config:
            return None

        extra = {}
        if config.extra_config:
            try:
                extra = json.loads(config.extra_config)
            except json.JSONDecodeError:
                extra = {}

        provider = (config.provider or '').lower()
        if provider in ['aliyun', 'tencent', 'azure', 'custom']:
            provider = 'openai'
        if provider not in ['openai', 'baidu']:
            provider = 'openai'

        service_config = {
            'service_type': provider,
            'api_key': config.api_key,
            'base_url': config.base_url,
            'model': extra.get('model') or extra.get('model_name') or 'whisper-1'
        }
        if config.api_secret:
            service_config['secret_key'] = config.api_secret
        return service_config
    except Exception as e:
        logger.warning(f"从系统服务配置获取STT配置失败: {str(e)}")
    return None


class STTService:
    """语音转文字服务基类"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}

    def transcribe_audio(self, audio_file_path: str, **kwargs) -> str:
        """
        将音频文件转换为文字

        Args:
            audio_file_path: 音频文件路径
            **kwargs: 额外参数

        Returns:
            str: 转换后的文字内容

        Raises:
            STTError: 语音转文字失败
        """
        raise NotImplementedError("子类必须实现此方法")


class OpenAISTTService(STTService):
    """OpenAI Whisper语音转文字服务"""

    def __init__(
            self,
            api_key: Optional[str] = None,
            base_url: Optional[str] = None,
            model: Optional[str] = None):
        super().__init__()
        self.model = model or 'whisper-1'
        # 优先使用传入的参数，其次从数据库获取
        if api_key:
            self.api_key = api_key
        else:
            db_config = get_stt_config_from_db()
            self.api_key = db_config.get('api_key') if db_config else None

        if base_url:
            self.base_url = base_url
        else:
            db_config = get_stt_config_from_db()
            self.base_url = (db_config.get('base_url') if db_config else None) or 'https://api.openai.com/v1'

    def transcribe_audio(self, audio_file_path: str, **kwargs) -> str:
        """使用OpenAI Whisper API进行语音转文字"""
        if not self.api_key:
            raise STTError("OpenAI API密钥未配置")

        if not os.path.exists(audio_file_path):
            raise STTError("音频文件不存在，请检查音频文件配置")

        try:
            # 检查文件大小限制（OpenAI限制25MB）
            file_size = os.path.getsize(audio_file_path)
            if file_size > 25 * 1024 * 1024:  # 25MB
                raise STTError("音频文件过大，超过25MB限制")

            # 准备API请求
            url = f"{self.base_url}/audio/transcriptions"
            headers = {
                'Authorization': f'Bearer {self.api_key}',
            }

            with open(audio_file_path, 'rb') as audio_file:
                files = {
                    'file': audio_file,
                    'model': (None, kwargs.get('model', self.model)),
                    'language': (None, kwargs.get('language', 'zh')),
                    'response_format': (None, 'text'),
                }

                response = requests.post(
                    url, headers=headers, files=files, timeout=60)

                if response.status_code == 200:
                    return response.text.strip()
                else:
                    logger.error(f"OpenAI语音转文字失败: {response.status_code} - {response.text}")
                    raise STTError("OpenAI语音转文字失败，请检查模型配置后重试")

        except requests.exceptions.RequestException as e:
            logger.error(f"网络请求失败: {str(e)}")
            raise STTError("语音转文字网络请求失败，请检查网络或模型配置后重试")
        except STTError:
            raise
        except Exception as e:
            logger.error(f"语音转文字处理失败: {str(e)}")
            raise STTError("语音转文字处理失败，请检查音频文件或模型配置后重试")


class BaiduSTTService(STTService):
    """百度语音识别服务"""

    def __init__(
            self,
            api_key: Optional[str] = None,
            secret_key: Optional[str] = None):
        super().__init__()
        # 优先使用传入的参数，其次从数据库获取
        if api_key:
            self.api_key = api_key
        else:
            db_config = get_stt_config_from_db()
            self.api_key = db_config.get('api_key') if db_config else None

        if secret_key:
            self.secret_key = secret_key
        else:
            db_config = get_stt_config_from_db()
            self.secret_key = db_config.get('secret_key') if db_config else None
        self.token_url = "https://aip.baidubce.com/oauth/2.0/token"
        self.stt_url = "https://aip.baidubce.com/rpc/2.0/aasr/v1/create"

    def _get_access_token(self) -> str:
        """获取百度API访问令牌"""
        params = {
            'grant_type': 'client_credentials',
            'client_id': self.api_key,
            'client_secret': self.secret_key
        }

        response = requests.get(self.token_url, params=params)
        if response.status_code == 200:
            result = response.json()
            return result.get('access_token', '')
        else:
            logger.error(f"获取百度API令牌失败: {response.text}")
            raise STTError("获取百度API令牌失败，请检查百度语音识别配置")

    def transcribe_audio(self, audio_file_path: str, **kwargs) -> str:
        """使用百度语音识别API进行语音转文字"""
        if not self.api_key or not self.secret_key:
            raise STTError("百度API密钥未配置")

        if not os.path.exists(audio_file_path):
            raise STTError("音频文件不存在，请检查音频文件配置")

        try:
            access_token = self._get_access_token()

            # 读取音频文件
            with open(audio_file_path, 'rb') as audio_file:
                audio_data = audio_file.read()

            # 准备请求数据
            import base64
            data = {
                'format': self._get_audio_format(audio_file_path),
                'rate': 16000,  # 采样率
                'channel': 1,   # 声道数
                'cuid': 'dtcall_system',
                'token': access_token,
                'speech': base64.b64encode(audio_data).decode('utf-8'),
                'len': len(audio_data)
            }

            response = requests.post(self.stt_url, data=data, timeout=30)

            if response.status_code == 200:
                result = response.json()
                if result.get('err_no') == 0:
                    return result.get('result', [''])[0]
                else:
                    logger.error(f"百度语音识别失败: {result.get('err_msg', '未知错误')}")
                    raise STTError("百度语音识别失败，请检查音频文件或服务配置")
            else:
                logger.error(f"百度API请求失败: {response.status_code}")
                raise STTError("百度API请求失败，请检查百度语音识别配置")

        except STTError:
            raise
        except Exception as e:
            logger.error(f"百度语音转文字失败: {str(e)}")
            raise STTError("百度语音转文字失败，请检查音频文件或服务配置后重试")

    def _get_audio_format(self, file_path: str) -> str:
        """根据文件扩展名获取音频格式"""
        ext = os.path.splitext(file_path)[1].lower()
        format_map = {
            '.wav': 'wav',
            '.pcm': 'pcm',
            '.amr': 'amr',
            '.m4a': 'm4a',
        }
        return format_map.get(ext, 'wav')


class LocalSTTService(STTService):
    """本地语音转文字服务（使用开源模型）"""

    def __init__(self, model_path: Optional[str] = None):
        super().__init__()
        self.model_path = model_path
        self._recognizer = None
        self._init_recognizer()

    def _init_recognizer(self):
        """初始化语音识别器"""
        try:
            import speech_recognition as sr
            self._recognizer = sr.Recognizer()
            logger.info("本地语音识别器初始化成功")
        except ImportError as e:
            logger.error(f"SpeechRecognition库未安装: {str(e)}")
            raise STTError("SpeechRecognition库未安装，请安装依赖")
        except Exception as e:
            logger.error(f"语音识别器初始化失败: {str(e)}")
            raise STTError("语音识别器初始化失败，请检查本地语音识别环境")

    def _convert_audio_format(self, audio_file_path: str) -> str:
        """将音频文件转换为WAV格式（如果需要）"""
        try:
            from pydub import AudioSegment
            import tempfile
            import os

            # 检查文件格式
            file_ext = os.path.splitext(audio_file_path)[1].lower()

            # 如果已经是WAV格式，直接返回原路径
            if file_ext == '.wav':
                return audio_file_path

            # 创建临时WAV文件
            temp_dir = tempfile.gettempdir()
            temp_wav_path = os.path.join(
                temp_dir, f"temp_converted_{os.path.basename(audio_file_path)}.wav")

            # 转换音频格式
            audio = AudioSegment.from_file(audio_file_path)
            audio = audio.set_frame_rate(16000)  # 设置采样率为16kHz
            audio = audio.set_channels(1)  # 设置为单声道
            audio.export(temp_wav_path, format='wav')

            logger.info(f"音频文件已转换为WAV格式: {temp_wav_path}")
            return temp_wav_path

        except ImportError:
            logger.warning("pydub库未安装，跳过音频格式转换")
            return audio_file_path
        except Exception as e:
            logger.warning(f"音频格式转换失败: {str(e)}")
            return audio_file_path

    def transcribe_audio(self, audio_file_path: str, **kwargs) -> str:
        """使用本地模型进行语音转文字"""
        if not os.path.exists(audio_file_path):
            raise STTError("音频文件不存在，请检查音频文件配置")

        try:
            import speech_recognition as sr

            # 转换音频格式为WAV（如果需要）
            converted_path = self._convert_audio_format(audio_file_path)

            # 使用SpeechRecognition进行语音识别
            with sr.AudioFile(converted_path) as source:
                # 调整环境噪音
                self._recognizer.adjust_for_ambient_noise(source, duration=0.5)

                # 读取音频数据
                audio_data = self._recognizer.record(source)

                # 尝试使用离线识别（PocketSphinx）
                try:
                    text = self._recognizer.recognize_sphinx(
                        audio_data, language='zh-CN')
                    logger.info("使用PocketSphinx离线识别成功")
                    return text
                except sr.UnknownValueError:
                    logger.warning("PocketSphinx无法识别音频内容")
                    raise STTError("本地离线语音识别未识别到内容，请检查音频质量或配置内网语音识别服务")
                except Exception as e:
                    logger.warning(f"PocketSphinx识别失败: {str(e)}")
                    raise STTError("本地离线语音识别失败，请检查音频文件或配置内网语音识别服务")

        except ImportError as e:
            logger.error(f"语音识别库未安装: {str(e)}")
            raise STTError("语音识别库未安装，请安装依赖")
        except Exception as e:
            logger.error(f"本地语音转文字失败: {str(e)}")
            raise STTError("本地语音转文字失败，请检查音频文件或本地识别环境")
        finally:
            # 清理临时文件
            if 'converted_path' in locals() and converted_path != audio_file_path:
                try:
                    if os.path.exists(converted_path):
                        os.remove(converted_path)
                        logger.info(f"已清理临时文件: {converted_path}")
                except Exception as e:
                    logger.warning(f"清理临时文件失败: {str(e)}")


class FreeSTTService(STTService):
    """免费语音转文字服务（使用开源API或本地模型）"""

    def __init__(self, service_type: str = None):
        super().__init__()
        # 优先使用传入的service_type，其次使用settings中的配置
        if service_type is None:
            self.service_type = getattr(
                settings, 'FREE_STT_SERVICE_TYPE', 'local')
        else:
            self.service_type = service_type
        self._fallback_services = []
        # 初始化备用服务
        self._init_fallback_services()

    def _init_fallback_services(self):
        """初始化备用服务列表"""
        # 按优先级顺序添加备用服务
        if self.service_type == 'local':
            # 优先尝试本地服务
            try:
                # 检查是否安装了SpeechRecognition库
                pass
                # 优先使用本地离线识别
                self._fallback_services.append('local_offline')
            except ImportError:
                logger.warning("SpeechRecognition库未安装，无法使用本地语音识别")

        # 添加其他可能的免费服务
        self._fallback_services.append('mock')  # 模拟服务作为最后备选

    def transcribe_audio(self, audio_file_path: str, **kwargs) -> str:
        """使用免费服务进行语音转文字"""
        if not os.path.exists(audio_file_path):
            raise STTError("音频文件不存在，请检查音频文件配置")

        # 检查文件大小
        file_size = os.path.getsize(audio_file_path)
        max_size = getattr(settings, 'STT_MAX_FILE_SIZE', 25 * 1024 * 1024)
        if file_size > max_size:
            raise STTError(f"音频文件过大，超过{max_size // (1024 * 1024)}MB限制")

        # 按优先级尝试不同的免费服务
        for service_name in self._fallback_services:
            try:
                if service_name == 'local_offline':
                    return self._transcribe_local_offline(
                        audio_file_path, **kwargs)
                elif service_name == 'speech_recognition':
                    return self._transcribe_with_speech_recognition(
                        audio_file_path, **kwargs)
                elif service_name == 'mock':
                    return self._transcribe_with_mock(
                        audio_file_path, **kwargs)
            except Exception as e:
                logger.warning(f"免费语音转文字服务 {service_name} 失败: {str(e)}")
                continue

        # 所有服务都失败
        raise STTError("所有免费语音转文字服务均不可用")

    def _transcribe_local_offline(self, audio_file_path: str, **kwargs) -> str:
        """使用本地离线语音识别（PocketSphinx）"""
        try:
            import speech_recognition as sr

            # 创建识别器
            r = sr.Recognizer()

            # 使用WAV文件
            with sr.AudioFile(audio_file_path) as source:
                # 调整环境噪音
                r.adjust_for_ambient_noise(source, duration=0.5)
                audio = r.record(source)

            # 使用Sphinx离线识别
            text = r.recognize_sphinx(audio, language='zh-CN')
            logger.info("本地离线语音识别成功")
            return text

        except sr.UnknownValueError:
            raise STTError("本地离线识别无法识别音频内容")
        except Exception as e:
            logger.warning(f"本地离线语音识别失败: {str(e)}")
            raise STTError("本地离线语音识别失败，请检查音频文件或本地识别环境")

    def _transcribe_with_speech_recognition(
            self, audio_file_path: str, **kwargs) -> str:
        """使用SpeechRecognition库进行语音转文字（兼容旧版本）"""
        try:
            # 优先尝试本地离线识别
            return self._transcribe_local_offline(audio_file_path, **kwargs)
        except Exception as e:
            logger.warning(f"本地离线识别失败: {str(e)}")
            raise STTError("本地离线语音识别失败，请配置内网语音识别服务")

    def _transcribe_with_mock(self, audio_file_path: str, **kwargs) -> str:
        """语音转文字服务（已移除模拟实现）"""
        raise STTError("模拟服务已移除，请使用正式的语音转文字服务")


class STTServiceFactory:
    """语音转文字服务工厂"""

    @staticmethod
    def create_service(service_type: str, **kwargs) -> STTService:
        """
        创建语音转文字服务实例

        Args:
            service_type: 服务类型，支持 'openai', 'baidu', 'local', 'free'
            **kwargs: 服务特定参数

        Returns:
            STTService实例
        """
        if service_type == 'openai':
            return OpenAISTTService(
                api_key=kwargs.get('api_key'),
                base_url=kwargs.get('base_url'),
                model=kwargs.get('model')
            )
        elif service_type == 'baidu':
            return BaiduSTTService(
                api_key=kwargs.get('api_key'),
                secret_key=kwargs.get('secret_key')
            )
        elif service_type == 'local':
            return LocalSTTService(model_path=kwargs.get('model_path'))
        elif service_type == 'free':
            # FreeSTTService只接受service_type参数，过滤掉其他参数
            service_kwargs = {}
            if 'service_type' in kwargs:
                service_kwargs['service_type'] = kwargs['service_type']
            return FreeSTTService(**service_kwargs)
        else:
            raise ValueError(f"不支持的语音转文字服务类型: {service_type}")


class STTError(Exception):
    """语音转文字服务异常"""


def transcribe_audio_file(
        audio_file_path: str,
        service_type: str = 'auto',
        **kwargs) -> str:
    """
    便捷函数：使用指定服务类型转写音频文件

    Args:
        audio_file_path: 音频文件路径
        service_type: 服务类型 ('auto', 'openai', 'baidu', 'local', 'free')
        **kwargs: 服务特定参数

    Returns:
        str: 转写后的文本
    """
    if service_type == 'auto':
        configured_service = get_configured_stt_service() or get_stt_config_from_db()
        if configured_service:
            service_type = configured_service.pop('service_type', 'openai')
            kwargs = {**configured_service, **kwargs}
        else:
            service_type = getattr(settings, 'DEFAULT_STT_SERVICE', 'free')

    service = STTServiceFactory.create_service(service_type, **kwargs)
    try:
        return service.transcribe_audio(audio_file_path, **kwargs)
    except STTError as exc:
        if service_type == 'free':
            raise STTError(
                "当前未配置可用的语音转文字服务。请在系统服务配置中启用STT服务，或配置支持音频转写的AI模型。"
            ) from exc
        raise
