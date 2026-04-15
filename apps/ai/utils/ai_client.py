import requests
import time
import logging
from apps.ai.models import AIModelConfig

logger = logging.getLogger(__name__)


class AIClientError(Exception):
    """AI客户端错误"""


class BaseAIClient:
    """AI模型客户端基类"""

    def __init__(
            self,
            provider=None,
            base_url=None,
            api_key=None,
            model_config=None):
        self.provider = provider or 'openai'

        # 只使用传入的配置参数，不依赖settings配置
        self.api_key = api_key or ''
        self.base_url = base_url or ''
        self.api_base = base_url or ''  # 添加 api_base 属性
        self.model_config = model_config or {}
        self.provider_specific_config = {}

        # 如果model_config是数据库模型配置对象，则使用其配置
        if model_config:
            # 判断是字典还是模型对象
            if hasattr(
                    model_config,
                    'api_key') and hasattr(
                    model_config,
                    'api_base'):
                # Django 模型对象
                self.api_key = model_config.api_key or self.api_key
                self.base_url = model_config.api_base or self.base_url
                self.api_base = model_config.api_base or self.api_base
                self.model_name = model_config.model_name or ''
                # 更新 model_config 字典以便 chat_completion 使用
                if isinstance(self.model_config, dict):
                    self.model_config['chat'] = model_config.model_name or ''
            elif isinstance(model_config, dict):
                # 字典配置
                self.api_key = model_config.get('api_key') or self.api_key
                self.base_url = model_config.get(
                    'api_base') or model_config.get('base_url') or self.base_url
                self.api_base = model_config.get(
                    'api_base') or model_config.get('base_url') or self.api_base
                self.model_name = model_config.get('model_name') or ''
                # 更新 model_config['chat'] 以便 chat_completion 使用
                if isinstance(self.model_config,
                              dict) and 'chat' not in self.model_config:
                    self.model_config['chat'] = model_config.get(
                        'model_name') or ''

        # 请求配置
        self.timeout = 60
        self.max_retries = 3
        self.retry_delay = 2

    def _make_request(self, method, url, **kwargs):
        """通用请求方法，包含重试机制"""
        for attempt in range(self.max_retries + 1):
            try:
                response = requests.request(
                    method, url, timeout=self.timeout, **kwargs
                )
                response.raise_for_status()
                return response
            except requests.exceptions.RequestException as e:
                if attempt == self.max_retries:
                    raise AIClientError(f"请求失败: {str(e)}")
                time.sleep(self.retry_delay * (2 ** attempt))  # 指数退避

    def _parse_chat_response(self, result, kwargs):
        """解析聊天完成响应，支持返回工具调用或纯文本"""
        if not result.get('choices'):
            return ""
        message = result['choices'][0].get('message', {})
        if "tools" in kwargs or kwargs.get("raw_message"):
            return message
        return message.get('content', '') or ""

    def chat_completion(self, messages, **kwargs):
        """生成聊天完成内容"""
        raise NotImplementedError("子类必须实现此方法")

    def text_completion(self, prompt, **kwargs):
        """生成文本完成内容"""
        raise NotImplementedError("子类必须实现此方法")

    def embedding(self, text, **kwargs):
        """生成文本嵌入向量"""
        raise NotImplementedError("子类必须实现此方法")

    def summarize_text(self, text, max_length=500, **kwargs):
        """文本摘要生成"""
        prompt = f"请将以下文本总结为不超过{max_length}字的内容：\n\n{text}"

        messages = [
            {'role': 'system', 'content': '你是一个专业的文本摘要助手。请根据用户提供的文本，生成简洁、准确的摘要。'},
            {'role': 'user', 'content': prompt}
        ]

        try:
            response = self.chat_completion(messages, **kwargs)
            return response
        except Exception as e:
            raise AIClientError(f"文本摘要生成失败: {str(e)}")

    def analyze_sentiment(self, text, **kwargs):
        """情感分析"""
        prompt = f"请分析以下文本的情感倾向（积极、消极或中性），并给出情感得分（-1到1之间）：\n\n{text}"

        messages = [
            {'role': 'system', 'content': '你是一个情感分析专家。请分析用户提供的文本情感，并返回情感类型和得分。'},
            {'role': 'user', 'content': prompt}
        ]

        try:
            response = self.chat_completion(messages, **kwargs)
            return response
        except Exception as e:
            raise AIClientError(f"情感分析失败: {str(e)}")

    def generate_content(self, prompt, **kwargs):
        """通用内容生成"""
        messages = [
            {'role': 'system', 'content': '你是一个内容生成助手，可以根据用户的需求生成各种类型的内容。'},
            {'role': 'user', 'content': prompt}
        ]

        try:
            response = self.chat_completion(messages, **kwargs)
            return response
        except Exception as e:
            raise AIClientError(f"内容生成失败: {str(e)}")


class OpenAIClient(BaseAIClient):
    """OpenAI客户端实现"""

    def __init__(self, base_url=None, api_key=None, model_config=None):
        # 调用父类初始化
        super().__init__(
            provider='openai',
            base_url=base_url,
            api_key=api_key,
            model_config=model_config)

        # 延迟初始化，避免启动时的错误
        self.client = None
        self.chat_completion_function = None
        self._openai = None  # 延迟导入

    def _ensure_client(self):
        """懒加载OpenAI客户端"""
        if self.client is not None:
            return True

        # 尝试导入OpenAI
        if self._openai is None:
            try:
                import openai
                self._openai = openai
            except ImportError:
                return False

        # 获取配置
        api_key = self.api_key
        if not api_key:
            return False

        # 创建客户端（只使用api_key参数）
        try:
            # 最简单的客户端创建方式
            self.client = self._openai.OpenAI(api_key=api_key)

            # 尝试设置base_url（如果有）
            base_url = self.base_url
            if base_url and hasattr(self.client, 'base_url'):
                self.client.base_url = base_url

            # 尝试获取旧版API调用函数
            try:
                self.chat_completion_function = self._openai.ChatCompletion.create
            except (AttributeError, TypeError):
                pass

            return True
        except Exception as e:
            logger.error(f"创建OpenAI客户端失败: {str(e)}")
            return False

    def _rest_url(self, path: str) -> str:
        base = (self.base_url or "https://api.openai.com/v1").rstrip("/")
        if not base.endswith("/v1") and "/v1/" not in (base + "/"):
            base = base + "/v1"
        return f"{base}/{path.lstrip('/')}"

    def _rest_chat_completion(self, messages, **kwargs):
        if not self.api_key:
            raise AIClientError("OpenAI API Key 未配置")
        url = self._rest_url("/chat/completions")
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        data = {
            "model": self.model_config.get("chat", "gpt-3.5-turbo"),
            "messages": messages,
            "temperature": kwargs.get("temperature", 0.7),
            "max_tokens": kwargs.get("max_tokens", 2000),
        }
        for k in ["top_p", "presence_penalty", "frequency_penalty", "stream", "tools", "tool_choice"]:
            if k in kwargs:
                data[k] = kwargs[k]
        try:
            response = self._make_request("POST", url, headers=headers, json=data)
            result = response.json()
            return self._parse_chat_response(result, kwargs)
        except Exception as e:
            raise AIClientError(f"OpenAI REST 调用失败：{str(e)}")

    def _rest_embedding(self, text, **kwargs):
        if not self.api_key:
            raise AIClientError("OpenAI API Key 未配置")
        url = self._rest_url("/embeddings")
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        data = {
            "model": kwargs.get(
                "model",
                self.model_config.get("embedding", "text-embedding-3-small"),
            ),
            "input": text,
        }
        try:
            response = self._make_request("POST", url, headers=headers, json=data)
            result = response.json()
            return result["data"][0]["embedding"]
        except Exception as e:
            raise AIClientError(f"OpenAI REST 嵌入请求失败: {str(e)}")

    def _call_responses_api(self, messages, params):
        """调用新的 /v1/responses API"""
        # 服务商支持的模型名称列表
        fallback_models = [
            'gpt-5.4',
            'gpt-5.3-codex',
            'gpt-5.2-codex',
            'gpt-5.1-codex',
            'gpt-5-codex']
        current_model = params.get('model', 'gpt-5.4')

        try:
            response = self.client.responses.create(
                model=current_model,
                input=messages,
                temperature=params.get('temperature', 0.7),
                max_output_tokens=params.get('max_tokens', 2000),
            )
            if hasattr(response, 'output') and response.output:
                for item in response.output:
                    if hasattr(item, 'content') and item.content:
                        if isinstance(item.content, list):
                            for content_item in item.content:
                                if hasattr(content_item, 'text'):
                                    return content_item.text
                        elif hasattr(item.content, 'text'):
                            return item.content.text
            if hasattr(response, 'text'):
                return response.text
            return str(response)
        except Exception as e:
            error_msg = str(e)
            # 如果是 502 错误且包含 "unknown provider"，尝试备用模型
            if '502' in error_msg and 'unknown provider' in error_msg.lower():
                for fallback_model in fallback_models:
                    if fallback_model != current_model:
                        try:
                            params['model'] = fallback_model
                            response = self.client.responses.create(**params)
                            if hasattr(response, 'output') and response.output:
                                for item in response.output:
                                    if hasattr(
                                            item, 'content') and item.content:
                                        if isinstance(item.content, list):
                                            for content_item in item.content:
                                                if hasattr(
                                                        content_item, 'text'):
                                                    return f"[使用模型 {fallback_model}] " + \
                                                        content_item.text
                                        elif hasattr(item.content, 'text'):
                                            return f"[使用模型 {fallback_model}] " + \
                                                item.content.text
                            if hasattr(response, 'text'):
                                return f"[使用模型 {fallback_model}] " + \
                                    response.text
                        except Exception:
                            continue
                raise AIClientError(
                    f"Responses API 调用失败：未找到可用的模型。请检查模型名称是否正确。错误详情：{error_msg}")
            raise AIClientError(f"Responses API 调用失败：{error_msg}")

    def chat_completion(self, messages, **kwargs):
        """生成聊天完成内容"""
        params = {
            'model': self.model_config.get('chat', 'gpt-3.5-turbo'),
            'temperature': kwargs.get('temperature', 0.7),
            'max_tokens': kwargs.get('max_tokens', 2000),
            'messages': messages
        }
        params.update(kwargs)

        if not self._ensure_client():
            return self._rest_chat_completion(messages, **kwargs)

        try:
            # 尝试顺序：
            # 1. 新的 Responses API (/v1/responses)
            # 2. Chat Completions API (/v1/chat/completions)
            # 3. 旧版 ChatCompletion.create
            try:
                return self._call_responses_api(messages, params)
            except Exception as responses_error:
                try:
                    response = self.client.chat.completions.create(**params)
                    if "tools" in kwargs or kwargs.get("raw_message"):
                        return response.choices[0].message
                    return response.choices[0].message.content
                except Exception as chat_error:
                    try:
                        old_params = params.copy()
                        if 'messages' in old_params:
                            old_params['messages'] = messages
                        response = self._openai.ChatCompletion.create(
                            **old_params)
                        if "tools" in kwargs or kwargs.get("raw_message"):
                            return response['choices'][0]['message']
                        return response['choices'][0]['message']['content']
                    except Exception:
                        raise responses_error
        except Exception as e:
            raise AIClientError(f"OpenAI API 调用失败：{str(e)}")

    def text_completion(self, prompt, **kwargs):
        """生成文本完成内容"""
        params = {
            'model': self.model_config.get('chat', 'gpt-3.5-turbo'),
            'temperature': kwargs.get('temperature', 0.7),
            'max_tokens': kwargs.get('max_tokens', 2000),
        }
        params.update(kwargs)

        # 懒加载客户端
        if not self._ensure_client():
            raise AIClientError("无法初始化OpenAI客户端")

        try:
            # 对于较新的API版本，使用ChatCompletion
            if 'gpt' in params.get('model', ''):
                messages = [{'role': 'user', 'content': prompt}]
                return self.chat_completion(messages, **params)
            else:
                # 对于旧版API，使用self._openai而不是直接引用openai
                params['prompt'] = prompt
                response = self._openai.Completion.create(**params)
                return response['choices'][0]['text']
        except Exception as e:
            raise AIClientError(f"OpenAI文本生成失败: {str(e)}")

    def embedding(self, text, **kwargs):
        """生成文本嵌入向量"""
        params = {
            'model': kwargs.get(
                'model',
                self.model_config.get(
                    'embedding',
                    'text-embedding-ada-002')),
            'input': text}

        # 懒加载客户端
        if not self._ensure_client():
            return self._rest_embedding(text, **kwargs)

        try:
            response = self._openai.Embedding.create(**params)
            return response['data'][0]['embedding']
        except Exception as e:
            raise AIClientError(f"OpenAI嵌入向量请求失败: {str(e)}")


class QwenClient(BaseAIClient):
    """阿里千问客户端实现（兼容OpenAI格式）"""

    def __init__(self, base_url=None, api_key=None, model_config=None):
        # 处理阿里千问API地址，确保使用兼容OpenAI格式的地址
        if base_url and 'dashscope.aliyuncs.com' in base_url and '/compatible-mode' not in base_url:
            # 替换为兼容OpenAI格式的地址
            base_url = 'https://dashscope.aliyuncs.com/compatible-mode/v1'
        super().__init__(
            provider='qwen',
            base_url=base_url,
            api_key=api_key,
            model_config=model_config)
        self.app_id = self.provider_specific_config.get('app_id', '')

    def chat_completion(self, messages, **kwargs):
        """生成聊天完成内容（兼容OpenAI格式）"""
        # 如果base_url已经包含完整路径，则直接使用base_url
        if self.base_url and '/chat/completions' in self.base_url:
            url = self.base_url
        else:
            url = f"{self.base_url}/chat/completions"

        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
        }

        data = {
            'model': self.model_config.get('chat', 'qwen-turbo'),
            'messages': messages,
            'temperature': kwargs.get('temperature', 0.7),
            'max_tokens': kwargs.get('max_tokens', 1024),
        }
        data.update(kwargs)

        try:
            response = self._make_request(
                'POST', url, headers=headers, json=data)
            result = response.json()
            return self._parse_chat_response(result, kwargs)
        except Exception as e:
            raise AIClientError(f"千问聊天完成请求失败: {str(e)}")

    def text_completion(self, prompt, **kwargs):
        """生成文本完成内容"""
        messages = [{'role': 'user', 'content': prompt}]
        return self.chat_completion(messages, **kwargs)

    def embedding(self, text, **kwargs):
        """生成文本嵌入向量（兼容OpenAI格式）"""
        url = f"{self.base_url}/embeddings"
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
        }

        data = {
            'model': self.model_config.get('embedding', 'text-embedding-v1'),
            'input': text
        }
        data.update(kwargs)

        try:
            response = self._make_request(
                'POST', url, headers=headers, json=data)
            result = response.json()
            return result['data'][0]['embedding']
        except Exception as e:
            raise AIClientError(f"阿里千问嵌入向量请求失败: {str(e)}")


class DeepSeekClient(BaseAIClient):
    """DeepSeek客户端实现"""

    def __init__(self, base_url=None, api_key=None, model_config=None):
        super().__init__(
            provider='deepseek',
            base_url=base_url,
            api_key=api_key,
            model_config=model_config)
        self.organization = self.provider_specific_config.get(
            'organization', '')

    def chat_completion(self, messages, **kwargs):
        """生成聊天完成内容（优化版，确保快速响应）"""
        url = f"{self.base_url}/chat/completions"
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
        }
        if self.organization:
            headers['OpenAI-Organization'] = self.organization

        data = {
            'model': self.model_config.get('chat', 'deepseek-chat'),
            'messages': messages,
            'temperature': kwargs.get('temperature', 0.7),
            'max_tokens': kwargs.get('max_tokens', 2000),
        }
        data.update(kwargs)

        # 优化超时设置：总处理时间控制在30秒内
        original_timeout = self.timeout
        self.timeout = 30  # 30秒超时，确保整体流程在1分钟内完成

        try:
            response = self._make_request(
                'POST', url, headers=headers, json=data)
            result = response.json()
            return self._parse_chat_response(result, kwargs)
        except Exception as e:
            raise AIClientError(f"DeepSeek聊天完成请求失败: {str(e)}")
        finally:
            # 恢复原始超时设置
            self.timeout = original_timeout

    def text_completion(self, prompt, **kwargs):
        """生成文本完成内容"""
        messages = [{'role': 'user', 'content': prompt}]
        return self.chat_completion(messages, **kwargs)

    def embedding(self, text, **kwargs):
        """生成文本嵌入向量"""
        url = f"{self.base_url}/embeddings"
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
        }
        if self.organization:
            headers['OpenAI-Organization'] = self.organization

        data = {
            'model': self.model_config.get('embedding', 'deepseek-embedding'),
            'input': text
        }
        data.update(kwargs)

        try:
            response = self._make_request(
                'POST', url, headers=headers, json=data)
            result = response.json()
            return result['data'][0]['embedding']
        except Exception as e:
            raise AIClientError(f"DeepSeek嵌入向量请求失败: {str(e)}")


class DoubaoClient(BaseAIClient):
    """豆包客户端实现"""

    def __init__(self, base_url=None, api_key=None, model_config=None):
        super().__init__(
            provider='doubao',
            base_url=base_url,
            api_key=api_key,
            model_config=model_config)
        self.app_key = self.provider_specific_config.get('app_key', '')

    def chat_completion(self, messages, **kwargs):
        """生成聊天完成内容"""
        url = f"{self.base_url}/chat/completions"
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
            'X-AppKey': self.app_key,
        }

        data = {
            'model': self.model_config.get('chat', 'doubao-pro'),
            'messages': messages,
            'temperature': kwargs.get('temperature', 0.7),
            'max_tokens': kwargs.get('max_tokens', 2000),
        }
        data.update(kwargs)

        try:
            response = self._make_request(
                'POST', url, headers=headers, json=data)
            result = response.json()
            return self._parse_chat_response(result, kwargs)
        except Exception as e:
            raise AIClientError(f"豆包聊天完成请求失败: {str(e)}")

    def text_completion(self, prompt, **kwargs):
        """生成文本完成内容"""
        messages = [{'role': 'user', 'content': prompt}]
        return self.chat_completion(messages, **kwargs)

    def embedding(self, text, **kwargs):
        """生成文本嵌入向量"""
        url = f"{self.base_url}/embeddings"
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
            'X-AppKey': self.app_key,
        }

        data = {
            'model': self.model_config.get('embedding', 'doubao-embedding'),
            'input': text
        }
        data.update(kwargs)

        try:
            response = self._make_request(
                'POST', url, headers=headers, json=data)
            result = response.json()
            return result['data'][0]['embedding']
        except Exception as e:
            raise AIClientError(f"豆包嵌入向量请求失败: {str(e)}")


class WenxinClient(BaseAIClient):
    """文心一言客户端实现"""

    def __init__(self, base_url=None, api_key=None, model_config=None):
        super().__init__(
            provider='wenxin',
            base_url=base_url,
            api_key=api_key,
            model_config=model_config)
        self.secret_key = self.provider_specific_config.get('secret_key', '')
        self.access_token = self.provider_specific_config.get(
            'access_token', '')
        # 如果没有access_token，则通过API Key和Secret Key获取
        if not self.access_token and self.api_key and self.secret_key:
            self.access_token = self._get_access_token()

    def _get_access_token(self):
        """获取文心一言Access Token"""
        url = "https://aip.baidubce.com/oauth/2.0/token"
        params = {
            'grant_type': 'client_credentials',
            'client_id': self.api_key,
            'client_secret': self.secret_key
        }

        try:
            response = self._make_request('POST', url, params=params)
            result = response.json()
            return result.get('access_token', '')
        except Exception as e:
            raise AIClientError(f"获取文心一言Access Token失败: {str(e)}")

    def chat_completion(self, messages, **kwargs):
        """生成聊天完成内容"""
        if not self.access_token:
            raise AIClientError("文心一言Access Token未配置")

        url = f"{self.base_url}/wenxinworkshop/chat/eb-instant"
        headers = {
            'Content-Type': 'application/json',
        }

        # 转换消息格式为文心一言格式
        prompt = self._convert_messages_to_prompt(messages)

        data = {
            'messages': [
                {
                    'role': 'user',
                    'content': prompt
                }
            ],
            'temperature': kwargs.get('temperature', 0.7),
            'max_tokens': kwargs.get('max_tokens', 1024),
        }
        data.update(kwargs)

        # 添加access_token到URL参数
        url_with_token = f"{url}?access_token={self.access_token}"

        try:
            response = self._make_request(
                'POST', url_with_token, headers=headers, json=data)
            result = response.json()
            content = result.get('result', '')
            if "tools" in kwargs or kwargs.get("raw_message"):
                return {"content": content}
            return content
        except Exception as e:
            raise AIClientError(f"文心一言聊天完成请求失败: {str(e)}")

    def _convert_messages_to_prompt(self, messages):
        """将OpenAI格式消息转换为文心一言格式"""
        prompt = ""
        for message in messages:
            if message['role'] == 'user':
                prompt += f"用户: {message['content']}\n"
            elif message['role'] == 'assistant':
                prompt += f"助手: {message['content']}\n"
            elif message['role'] == 'system':
                prompt += f"系统: {message['content']}\n"
        return prompt.strip()

    def text_completion(self, prompt, **kwargs):
        """生成文本完成内容"""
        messages = [{'role': 'user', 'content': prompt}]
        return self.chat_completion(messages, **kwargs)

    def embedding(self, text, **kwargs):
        """生成文本嵌入向量"""
        if not self.access_token:
            raise AIClientError("文心一言Access Token未配置")

        url = f"{self.base_url}/rpc/2.0/ai_custom/v1/wenxinworkshop/embeddings/embedding-v1"
        headers = {
            'Content-Type': 'application/json',
        }

        data = {
            'input': [text]
        }
        data.update(kwargs)

        # 添加access_token到URL参数
        url_with_token = f"{url}?access_token={self.access_token}"

        try:
            response = self._make_request(
                'POST', url_with_token, headers=headers, json=data)
            result = response.json()
            return result.get('data', [{}])[0].get('embedding', [])
        except Exception as e:
            raise AIClientError(f"文心一言嵌入向量请求失败: {str(e)}")


class LocalModelClient(BaseAIClient):
    """本地大模型客户端实现"""

    def __init__(self, base_url=None, api_key=None, model_config=None):
        super().__init__(
            provider='local',
            base_url=base_url,
            api_key=api_key,
            model_config=model_config)
        self.local_config = {}  # 不再使用settings配置

    def chat_completion(self, messages, **kwargs):
        """生成聊天完成内容"""
        url = f"{self.base_url}/chat/completions"
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
        }

        data = {
            'model': self.model_config.get(
                'chat',
                'local-model'),
            'messages': messages,
            'temperature': kwargs.get(
                'temperature',
                self.local_config.get(
                    'temperature',
                    0.7)),
            'max_tokens': kwargs.get(
                'max_tokens',
                self.local_config.get(
                    'max_tokens',
                    4096)),
        }
        data.update(kwargs)

        try:
            response = self._make_request(
                'POST', url, headers=headers, json=data)
            result = response.json()
            return self._parse_chat_response(result, kwargs)
        except Exception as e:
            raise AIClientError(f"本地大模型聊天完成请求失败: {str(e)}")

    def text_completion(self, prompt, **kwargs):
        """生成文本完成内容"""
        messages = [{'role': 'user', 'content': prompt}]
        return self.chat_completion(messages, **kwargs)

    def embedding(self, text, **kwargs):
        """生成文本嵌入向量"""
        url = f"{self.base_url}/embeddings"
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
        }

        data = {
            'model': self.model_config.get('embedding', 'local-embedding'),
            'input': text
        }
        data.update(kwargs)

        try:
            response = self._make_request(
                'POST', url, headers=headers, json=data)
            result = response.json()
            return result['data'][0]['embedding']
        except Exception as e:
            raise AIClientError(f"本地大模型嵌入向量请求失败: {str(e)}")


class OllamaClient(BaseAIClient):
    def __init__(self, base_url=None, api_key=None, model_config=None):
        super().__init__(
            provider='ollama',
            base_url=base_url,
            api_key=api_key,
            model_config=model_config)

    def chat_completion(self, messages, **kwargs):
        if not self.base_url:
            raise AIClientError("Ollama base_url未配置")

        url = f"{self.base_url}/api/chat"
        headers = {'Content-Type': 'application/json'}

        options = {
            'temperature': kwargs.get('temperature', self.model_config.get('temperature', 0.7)),
            'top_p': kwargs.get('top_p', self.model_config.get('top_p', 1.0)),
            'num_predict': kwargs.get('max_tokens', self.model_config.get('max_tokens', 2048)),
        }

        data = {
            'model': self.model_config.get('chat', 'llama3'),
            'messages': messages,
            'stream': False,
            'options': options
        }

        try:
            response = self._make_request('POST', url, headers=headers, json=data)
            result = response.json()
            message = result.get('message', {})
            if "tools" in kwargs or kwargs.get("raw_message"):
                return message
            return message.get('content', '') or ""
        except Exception as e:
            raise AIClientError(f"Ollama聊天完成请求失败: {str(e)}")

    def text_completion(self, prompt, **kwargs):
        messages = [{'role': 'user', 'content': prompt}]
        return self.chat_completion(messages, **kwargs)

    def embedding(self, text, **kwargs):
        if not self.base_url:
            raise AIClientError("Ollama base_url未配置")

        url = f"{self.base_url}/api/embeddings"
        headers = {'Content-Type': 'application/json'}
        data = {
            'model': self.model_config.get('embedding', self.model_config.get('chat', 'llama3')),
            'prompt': text
        }
        data.update(kwargs)

        try:
            response = self._make_request('POST', url, headers=headers, json=data)
            result = response.json()
            return result.get('embedding', [])
        except Exception as e:
            raise AIClientError(f"Ollama嵌入向量请求失败: {str(e)}")


class AIClient:
    """AI模型客户端入口类"""

    def __init__(self, model_config_id=None, provider=None):
        # 支持从数据库模型配置初始化
        if model_config_id:
            try:
                self.model_config = AIModelConfig.objects.get(
                    id=model_config_id, is_active=True)
                self.provider = self.model_config.provider or provider or 'openai'
            except AIModelConfig.DoesNotExist:
                raise AIClientError(f"未找到ID为{model_config_id}的AI模型配置")
        else:
            self.provider = provider or 'openai'
            self.model_config = None

        # 根据提供商创建相应的客户端实例
        self.client = self._create_client()

    def _create_client(self):
        """根据提供商创建客户端实例"""
        # 准备传递给客户端的配置参数
        # 支持模型对象和字典两种格式
        if hasattr(self.model_config, 'api_base'):
            base_url = self.model_config.api_base
            api_key = self.model_config.api_key
            model_name = self.model_config.model_name
            temperature = self.model_config.temperature
            max_tokens = self.model_config.max_tokens
            top_p = self.model_config.top_p
        else:
            base_url = self.model_config.get(
                'api_base') if self.model_config else None
            api_key = self.model_config.get(
                'api_key') if self.model_config else None
            model_name = self.model_config.get(
                'model_name') if self.model_config else 'gpt-3.5-turbo'
            temperature = self.model_config.get(
                'temperature') if self.model_config else 0.7
            max_tokens = self.model_config.get(
                'max_tokens') if self.model_config else 2000
            top_p = self.model_config.get(
                'top_p') if self.model_config else 1.0

        model_config = {
            'chat': model_name,
            'temperature': temperature,
            'max_tokens': max_tokens,
            'top_p': top_p
        }

        if self.provider == 'openai':
            client = OpenAIClient(
                base_url=base_url,
                api_key=api_key,
                model_config=model_config)
        elif self.provider == 'qwen' or self.provider == 'alibaba':
            client = QwenClient(
                base_url=base_url,
                api_key=api_key,
                model_config=model_config)
        elif self.provider == 'deepseek':
            client = DeepSeekClient(
                base_url=base_url,
                api_key=api_key,
                model_config=model_config)
        elif self.provider == 'doubao':
            client = DoubaoClient(
                base_url=base_url,
                api_key=api_key,
                model_config=model_config)
        elif self.provider == 'wenxin' or self.provider == 'baidu':
            client = WenxinClient(
                base_url=base_url,
                api_key=api_key,
                model_config=model_config)
        elif self.provider == 'local':
            client = LocalModelClient(
                base_url=base_url,
                api_key=api_key,
                model_config=model_config)
        elif self.provider == 'ollama':
            client = OllamaClient(
                base_url=base_url,
                api_key=api_key,
                model_config=model_config)
        else:
            raise AIClientError(f"不支持的AI提供商: {self.provider}")

        # 如果存在模型配置，则应用配置到客户端
        if self.model_config:
            self._apply_model_config_to_client(client)

        return client

    def _apply_model_config_to_client(self, client):
        """将模型配置应用到客户端实例"""
        # 应用基础URL，处理阿里千问API地址格式
        if self.model_config.api_base:
            api_base = self.model_config.api_base
            # 对于阿里千问，确保使用兼容OpenAI格式的地址
            if client.provider in [
                'qwen',
                    'alibaba'] and 'dashscope.aliyuncs.com' in api_base and '/compatible-mode' not in api_base:
                # 替换为兼容OpenAI格式的地址
                client.base_url = 'https://dashscope.aliyuncs.com/compatible-mode/v1'
            else:
                client.base_url = api_base

        # 应用API密钥
        if self.model_config.api_key:
            client.api_key = self.model_config.api_key

        # 应用模型配置
        client.model_config['chat'] = self.model_config.model_name
        client.model_config['temperature'] = self.model_config.temperature
        client.model_config['max_tokens'] = self.model_config.max_tokens
        client.model_config['top_p'] = self.model_config.top_p

    # 代理方法到具体的客户端实例
    def chat_completion(self, messages, **kwargs):
        return self.client.chat_completion(messages, **kwargs)

    def text_completion(self, prompt, **kwargs):
        return self.client.text_completion(prompt, **kwargs)

    def embedding(self, text, **kwargs):
        return self.client.embedding(text, **kwargs)

    def summarize_text(self, text, max_length=500, **kwargs):
        return self.client.summarize_text(text, max_length, **kwargs)

    def analyze_sentiment(self, text, **kwargs):
        return self.client.analyze_sentiment(text, **kwargs)

    def generate_content(self, prompt, **kwargs):
        return self.client.generate_content(prompt, **kwargs)

    def generate(self, prompt, **kwargs):
        return self.generate_content(prompt, **kwargs)

    @classmethod
    def from_config(cls, config):
        """
        从配置字典创建AIClient实例

        Args:
            config: 配置字典，包含provider, api_key, base_url等字段

        Returns:
            AIClient: AIClient实例
        """
        if not config:
            raise AIClientError("配置不能为空")

        # 从配置中提取必要字段
        provider = config.get('provider')
        api_key = config.get('api_key')
        base_url = config.get('base_url') or config.get('api_base')

        # 创建客户端实例
        if provider == 'openai':
            return OpenAIClient(
                base_url=base_url,
                api_key=api_key,
                model_config=config)
        elif provider == 'qwen' or provider == 'alibaba':
            return QwenClient(
                base_url=base_url,
                api_key=api_key,
                model_config=config)
        elif provider == 'deepseek':
            return DeepSeekClient(
                base_url=base_url,
                api_key=api_key,
                model_config=config)
        elif provider == 'doubao':
            return DoubaoClient(
                base_url=base_url,
                api_key=api_key,
                model_config=config)
        elif provider == 'wenxin' or provider == 'baidu':
            return WenxinClient(
                base_url=base_url,
                api_key=api_key,
                model_config=config)
        elif provider == 'local':
            return LocalModelClient(
                base_url=base_url,
                api_key=api_key,
                model_config=config)
        elif provider == 'ollama':
            return OllamaClient(
                base_url=base_url,
                api_key=api_key,
                model_config=config)
        else:
            raise AIClientError(f"不支持的AI提供商: {provider}")
