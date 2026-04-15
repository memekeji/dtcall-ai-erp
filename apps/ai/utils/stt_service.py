"""
语音转文字服务模块
提供语音文件转文字功能，支持多种语音转文字服务
"""

import os
import logging
from typing import Optional, Dict, Any
import requests
from django.conf import settings

logger = logging.getLogger(__name__)


def get_stt_config_from_db():
    """从数据库获取语音转文字配置"""
    try:
        from apps.ai.models import AIModelConfig
        # 获取激活的AI配置
        active_configs = AIModelConfig.objects.filter(is_active=True)
        if active_configs.exists():
            config = active_configs.first()
            return {
                'api_key': config.api_key,
                'base_url': config.api_base,
                'provider': config.provider
            }
    except Exception as e:
        logger.warning(f"从数据库获取AI配置失败: {str(e)}")

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
            base_url: Optional[str] = None):
        super().__init__()
        # 优先使用传入的参数，其次从数据库获取，最后从settings获取
        if api_key:
            self.api_key = api_key
        else:
            # 尝试从数据库获取配置
            db_config = get_stt_config_from_db()
            if db_config and db_config.get('api_key'):
                self.api_key = db_config['api_key']
            else:
                self.api_key = getattr(settings, 'OPENAI_API_KEY', None)

        if base_url:
            self.base_url = base_url
        else:
            # 尝试从数据库获取配置
            db_config = get_stt_config_from_db()
            if db_config and db_config.get('base_url'):
                self.base_url = db_config['base_url']
            else:
                self.base_url = getattr(
                    settings, 'OPENAI_BASE_URL', 'https://api.openai.com/v1')

    def transcribe_audio(self, audio_file_path: str, **kwargs) -> str:
        """使用OpenAI Whisper API进行语音转文字"""
        if not self.api_key:
            raise STTError("OpenAI API密钥未配置")

        if not os.path.exists(audio_file_path):
            raise STTError(f"音频文件不存在: {audio_file_path}")

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
                    'model': (None, 'whisper-1'),
                    'language': (None, kwargs.get('language', 'zh')),
                    'response_format': (None, 'text'),
                }

                response = requests.post(
                    url, headers=headers, files=files, timeout=60)

                if response.status_code == 200:
                    return response.text.strip()
                else:
                    error_msg = f"OpenAI语音转文字失败: {response.status_code} - {response.text}"
                    logger.error(error_msg)
                    raise STTError(error_msg)

        except requests.exceptions.RequestException as e:
            error_msg = f"网络请求失败: {str(e)}"
            logger.error(error_msg)
            raise STTError(error_msg)
        except Exception as e:
            error_msg = f"语音转文字处理失败: {str(e)}"
            logger.error(error_msg)
            raise STTError(error_msg)


class BaiduSTTService(STTService):
    """百度语音识别服务"""

    def __init__(
            self,
            api_key: Optional[str] = None,
            secret_key: Optional[str] = None):
        super().__init__()
        # 优先使用传入的参数，其次从数据库获取，最后从settings获取
        if api_key:
            self.api_key = api_key
        else:
            # 尝试从数据库获取配置
            db_config = get_stt_config_from_db()
            if db_config and db_config.get('api_key'):
                self.api_key = db_config['api_key']
            else:
                self.api_key = getattr(settings, 'BAIDU_API_KEY', None)

        if secret_key:
            self.secret_key = secret_key
        else:
            # 尝试从数据库获取配置
            db_config = get_stt_config_from_db()
            if db_config and db_config.get('api_key'):
                # 对于百度服务，可能需要特殊处理secret_key
                self.secret_key = db_config.get('secret_key') or getattr(
                    settings, 'BAIDU_SECRET_KEY', None)
            else:
                self.secret_key = getattr(settings, 'BAIDU_SECRET_KEY', None)
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
            raise STTError(f"获取百度API令牌失败: {response.text}")

    def transcribe_audio(self, audio_file_path: str, **kwargs) -> str:
        """使用百度语音识别API进行语音转文字"""
        if not self.api_key or not self.secret_key:
            raise STTError("百度API密钥未配置")

        if not os.path.exists(audio_file_path):
            raise STTError(f"音频文件不存在: {audio_file_path}")

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
                    raise STTError(
                        f"百度语音识别失败: {result.get('err_msg', '未知错误')}")
            else:
                raise STTError(f"百度API请求失败: {response.status_code}")

        except Exception as e:
            error_msg = f"百度语音转文字失败: {str(e)}"
            logger.error(error_msg)
            raise STTError(error_msg)

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
            raise STTError(f"语音识别器初始化失败: {str(e)}")

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
            raise STTError(f"音频文件不存在: {audio_file_path}")

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
                    # 尝试使用Google语音识别（需要网络，但准确率更高）
                    try:
                        text = self._recognizer.recognize_google(
                            audio_data, language='zh-CN')
                        logger.info("使用Google语音识别成功")
                        return text
                    except sr.UnknownValueError:
                        raise STTError("无法识别音频内容")
                    except sr.RequestError as e:
                        logger.warning(f"Google语音识别服务不可用: {str(e)}")
                        raise STTError("语音识别服务不可用，请检查网络连接")
                except Exception as e:
                    logger.warning(f"PocketSphinx识别失败: {str(e)}")
                    # 如果离线识别失败，尝试Google识别
                    try:
                        text = self._recognizer.recognize_google(
                            audio_data, language='zh-CN')
                        logger.info("使用Google语音识别成功")
                        return text
                    except Exception as e2:
                        logger.error(f"所有语音识别方法均失败: {str(e2)}")
                        raise STTError(f"语音识别失败: {str(e2)}")

        except ImportError as e:
            logger.error(f"语音识别库未安装: {str(e)}")
            raise STTError("语音识别库未安装，请安装依赖")
        except Exception as e:
            logger.error(f"本地语音转文字失败: {str(e)}")
            raise STTError(f"本地语音转文字失败: {str(e)}")
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
                # 然后尝试Google在线识别
                self._fallback_services.append('google_online')
            except ImportError:
                logger.warning("SpeechRecognition库未安装，无法使用本地语音识别")

        # 添加其他可能的免费服务
        self._fallback_services.append('mock')  # 模拟服务作为最后备选

    def transcribe_audio(self, audio_file_path: str, **kwargs) -> str:
        """使用免费服务进行语音转文字"""
        if not os.path.exists(audio_file_path):
            raise STTError(f"音频文件不存在: {audio_file_path}")

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
                elif service_name == 'google_online':
                    return self._transcribe_google_online(
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
            raise STTError(f"本地离线语音识别失败: {str(e)}")

    def _transcribe_google_online(self, audio_file_path: str, **kwargs) -> str:
        """使用Google在线语音识别"""
        try:
            import speech_recognition as sr

            # 创建识别器
            r = sr.Recognizer()

            # 使用WAV文件
            with sr.AudioFile(audio_file_path) as source:
                audio = r.record(source)

            # 使用Google语音识别
            text = r.recognize_google(audio, language='zh-CN')
            logger.info("Google在线语音识别成功")
            return text

        except sr.UnknownValueError:
            raise STTError("Google语音识别无法识别音频内容")
        except sr.RequestError as e:
            logger.warning(f"Google语音识别服务不可用: {str(e)}")
            raise STTError("Google语音识别服务不可用，请检查网络连接")
        except Exception as e:
            logger.warning(f"Google语音识别失败: {str(e)}")
            raise STTError(f"Google语音识别失败: {str(e)}")

    def _transcribe_with_speech_recognition(
            self, audio_file_path: str, **kwargs) -> str:
        """使用SpeechRecognition库进行语音转文字（兼容旧版本）"""
        try:
            # 优先尝试本地离线识别
            return self._transcribe_local_offline(audio_file_path, **kwargs)
        except Exception as e:
            logger.warning(f"本地离线识别失败，尝试Google在线识别: {str(e)}")

            # 如果离线识别失败，尝试在线识别
            return self._transcribe_google_online(audio_file_path, **kwargs)

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
            return OpenAISTTService(**kwargs)
        elif service_type == 'baidu':
            return BaiduSTTService(**kwargs)
        elif service_type == 'local':
            return LocalSTTService(**kwargs)
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
        # 自动选择服务：优先使用配置的服务
        default_service = getattr(settings, 'DEFAULT_STT_SERVICE', 'free')
        service_type = default_service

    service = STTServiceFactory.create_service(service_type, **kwargs)
    return service.transcribe_audio(audio_file_path, **kwargs)
