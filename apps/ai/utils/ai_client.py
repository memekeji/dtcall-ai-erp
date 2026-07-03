import requests
import time
import logging
from apps.ai.models import AIModelConfig

logger = logging.getLogger(__name__)


SAFE_AI_ERROR_MESSAGE = "AI模型调用失败，请检查模型配置后重试"


class AIClientError(Exception):
    """AI客户端错误"""

    def __init__(self, message, *, error_code=None, status_code=None, detail=None):
        super().__init__(message)
        self.error_code = error_code
        self.status_code = status_code
        self.detail = detail or message


class BaseAIClient:
    """AI模型客户端基类"""

    def __init__(
            self,
            provider=None,
            base_url=None,
            api_key=None,
            model_config=None):
        self.provider = provider or 'openai'
        self.api_key = api_key or ''
        self.base_url = AIModelConfig.normalize_api_base(base_url or '')
        self.api_base = self.base_url
        self.model_config = model_config or {}
        self.provider_specific_config = {}
        if isinstance(model_config, dict):
            provider_specific_config = model_config.get(
                'provider_specific_config') or {}
            if isinstance(provider_specific_config, dict):
                self.provider_specific_config.update(provider_specific_config)
            for key in [
                    'organization',
                    'project',
                    'api_version',
                    'secret_key',
                    'access_token',
                    'anthropic_version']:
                if model_config.get(key):
                    self.provider_specific_config[key] = model_config.get(key)
        elif model_config:
            for key in ['organization', 'project']:
                if hasattr(model_config, key) and getattr(model_config, key):
                    self.provider_specific_config[key] = getattr(model_config, key)

        if model_config:
            if hasattr(
                    model_config,
                    'api_key') and hasattr(
                    model_config,
                    'api_base'):
                self.api_key = model_config.api_key or self.api_key
                self.base_url = model_config.base_url or self.base_url
                self.api_base = self.base_url
                primary_model = model_config.primary_model_name() if hasattr(
                    model_config, 'primary_model_name') else ''
                self.model_name = primary_model or ''
                if isinstance(self.model_config, dict):
                    self.model_config['chat'] = primary_model or ''
                    self.model_config['model_name'] = primary_model or ''
            elif isinstance(model_config, dict):
                self.api_key = model_config.get('api_key') or self.api_key
                self.base_url = AIModelConfig.normalize_api_base(
                    model_config.get('api_base') or model_config.get('base_url') or self.base_url
                )
                self.api_base = self.base_url
                primary_model = (
                    model_config.get('model_name')
                    or model_config.get('chat')
                    or (model_config.get('model_names') or [''])[0]
                )
                self.model_name = primary_model or ''
                if isinstance(self.model_config,
                              dict) and 'chat' not in self.model_config:
                    self.model_config['chat'] = primary_model or ''
                if isinstance(self.model_config, dict):
                    self.model_config['model_name'] = primary_model or ''

        self.timeout = 30
        self.max_retries = 1
        self.retry_delay = 1

    def _join_url(self, path, default_base=None):
        base = (self.base_url or default_base or '').rstrip('/')
        if not base:
            raise AIClientError("AI接口基础URL未配置")

        target_path = '/' + path.lstrip('/')
        target_suffix = target_path.rstrip('/')
        endpoint_suffixes = [
            '/chat/completions',
            '/embeddings',
            '/responses',
            '/messages',
            '/api/chat',
            '/api/embeddings'
        ]
        for suffix in endpoint_suffixes:
            if base.endswith(suffix):
                if suffix == target_suffix:
                    return base
                base = base[:-len(suffix)]
                break
        return f"{base}{target_path}"

    def _request_headers(self):
        if self.api_key:
            return {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json',
            }
        return {'Content-Type': 'application/json'}

    def _make_request(self, method, url, **kwargs):
        """通用请求方法，包含重试机制"""
        for attempt in range(self.max_retries + 1):
            try:
                response = requests.request(
                    method, url, timeout=self.timeout, **kwargs
                )
                response.raise_for_status()
                return response
            except requests.exceptions.HTTPError as e:
                if attempt == self.max_retries:
                    status_code = e.response.status_code if e.response is not None else None
                    detail = None
                    if e.response is not None:
                        try:
                            detail = e.response.text[:500]
                        except Exception:
                            detail = str(e)
                    logger.error(f"请求失败: {str(e)}")
                    raise AIClientError(
                        SAFE_AI_ERROR_MESSAGE,
                        error_code='http_error',
                        status_code=status_code,
                        detail=detail or str(e),
                    ) from None
                time.sleep(self.retry_delay * (2 ** attempt))
            except requests.exceptions.Timeout as e:
                if attempt == self.max_retries:
                    logger.error(f"请求超时: {str(e)}")
                    raise AIClientError(
                        SAFE_AI_ERROR_MESSAGE,
                        error_code='timeout',
                        detail=str(e),
                    ) from None
                time.sleep(self.retry_delay * (2 ** attempt))
            except requests.exceptions.ConnectionError as e:
                if attempt == self.max_retries:
                    logger.error(f"连接失败: {str(e)}")
                    raise AIClientError(
                        SAFE_AI_ERROR_MESSAGE,
                        error_code='connection_error',
                        detail=str(e),
                    ) from None
                time.sleep(self.retry_delay * (2 ** attempt))
            except requests.exceptions.RequestException as e:
                if attempt == self.max_retries:
                    logger.error(f"请求失败: {str(e)}")
                    raise AIClientError(
                        SAFE_AI_ERROR_MESSAGE,
                        error_code='request_error',
                        detail=str(e),
                    ) from None
                time.sleep(self.retry_delay * (2 ** attempt))

    def _raise_safe_error(self, message, error):
        logger.error(f"{message}: {str(error)}")
        if isinstance(error, AIClientError):
            raise error
        raise AIClientError(
            SAFE_AI_ERROR_MESSAGE,
            error_code='client_error',
            detail=str(error),
        ) from None

    def _parse_chat_response(self, result, kwargs):
        """解析聊天完成响应"""
        if not result.get('choices'):
            return ""
        message = result['choices'][0].get('message', {})
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
            self._raise_safe_error("文本摘要生成失败", e)

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
            self._raise_safe_error("情感分析失败", e)

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
            self._raise_safe_error("内容生成失败", e)


class OpenAIClient(BaseAIClient):
    """OpenAI客户端实现"""

    def __init__(self, base_url=None, api_key=None, model_config=None):
        super().__init__(
            provider='openai',
            base_url=base_url,
            api_key=api_key,
            model_config=model_config)

        self.client = None
        self.chat_completion_function = None
        self._openai = None

    def _ensure_client(self):
        """懒加载OpenAI客户端"""
        if self.client is not None:
            return True

        if self._openai is None:
            try:
                import openai
                self._openai = openai
            except ImportError:
                return False

        api_key = self.api_key
        if not api_key:
            return False

        try:
            client_kwargs = {'api_key': api_key}
            if self.base_url:
                client_kwargs['base_url'] = self.base_url
            self.client = self._openai.OpenAI(**client_kwargs)

            try:
                self.chat_completion_function = self._openai.ChatCompletion.create
            except (AttributeError, TypeError):
                pass

            return True
        except Exception as e:
            logger.error(f"创建OpenAI客户端失败: {str(e)}")
            return False

    def _rest_url(self, path: str) -> str:
        return self._join_url(path, "https://api.openai.com/v1")

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
            "temperature": kwargs.get("temperature", self.model_config.get('temperature', 0.7)),
            "max_tokens": kwargs.get("max_tokens", self.model_config.get('max_tokens', 2000)),
        }
        for k in ["top_p", "presence_penalty", "frequency_penalty", "stream"]:
            if k in kwargs:
                data[k] = kwargs[k]
        try:
            response = self._make_request("POST", url, headers=headers, json=data)
            result = response.json()
            return self._parse_chat_response(result, kwargs)
        except Exception as e:
            self._raise_safe_error("OpenAI REST 调用失败", e)

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
            self._raise_safe_error("OpenAI REST 嵌入请求失败", e)

    def _call_responses_api(self, messages, params):
        """调用新的 /v1/responses API"""
        try:
            response = self.client.responses.create(
                model=params.get('model', 'gpt-3.5-turbo'),
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
            logger.error(f"Responses API 调用失败: {str(e)}")
            raise

    def chat_completion(self, messages, **kwargs):
        """生成聊天完成内容"""
        params = {
            'model': kwargs.get('model', self.model_config.get('chat', 'gpt-3.5-turbo')),
            'temperature': kwargs.get('temperature', self.model_config.get('temperature', 0.7)),
            'max_tokens': kwargs.get('max_tokens', self.model_config.get('max_tokens', 2000)),
            'messages': messages
        }
        if 'top_p' in kwargs or self.model_config.get('top_p') is not None:
            params['top_p'] = kwargs.get('top_p', self.model_config.get('top_p', 1.0))

        if not self._ensure_client():
            return self._rest_chat_completion(messages, **kwargs)

        try:
            try:
                response = self.client.chat.completions.create(**params)
                return response.choices[0].message.content
            except Exception as chat_error:
                try:
                    return self._rest_chat_completion(messages, **kwargs)
                except Exception as rest_error:
                    if self._is_official_endpoint():
                        try:
                            return self._call_responses_api(messages, params)
                        except Exception:
                            pass
                    logger.error(f"OpenAI Chat Completions 调用失败: {str(chat_error)}")
                    raise rest_error
        except Exception as e:
            self._raise_safe_error("OpenAI API 调用失败", e)

    def _is_official_endpoint(self):
        base_url = (self.base_url or 'https://api.openai.com/v1').lower()
        return 'api.openai.com' in base_url

    def text_completion(self, prompt, **kwargs):
        """生成文本完成内容"""
        messages = [{'role': 'user', 'content': prompt}]
        return self.chat_completion(messages, **kwargs)

    def embedding(self, text, **kwargs):
        """生成文本嵌入向量"""
        params = {
            'model': kwargs.get(
                'model',
                self.model_config.get(
                    'embedding',
                    'text-embedding-3-small')),
            'input': text}

        if not self._ensure_client():
            return self._rest_embedding(text, **kwargs)

        try:
            try:
                response = self.client.embeddings.create(**params)
                return response.data[0].embedding
            except Exception:
                return self._rest_embedding(text, **kwargs)
        except Exception as e:
            self._raise_safe_error("OpenAI嵌入向量请求失败", e)


class QwenClient(BaseAIClient):
    """阿里千问客户端实现（兼容OpenAI格式）"""

    def __init__(self, base_url=None, api_key=None, model_config=None):
        if base_url and 'dashscope.aliyuncs.com' in base_url and '/compatible-mode' not in base_url:
            base_url = 'https://dashscope.aliyuncs.com/compatible-mode/v1'
        super().__init__(
            provider='qwen',
            base_url=base_url,
            api_key=api_key,
            model_config=model_config)
        self.app_id = self.provider_specific_config.get('app_id', '')

    def chat_completion(self, messages, **kwargs):
        """生成聊天完成内容（兼容OpenAI格式）"""
        url = self._join_url('/chat/completions')
        headers = self._request_headers()

        data = {
            'model': self.model_config.get('chat', 'qwen-turbo'),
            'messages': messages,
            'temperature': kwargs.get('temperature', self.model_config.get('temperature', 0.7)),
            'max_tokens': kwargs.get('max_tokens', self.model_config.get('max_tokens', 1024)),
        }
        data.update(kwargs)

        try:
            response = self._make_request(
                'POST', url, headers=headers, json=data)
            result = response.json()
            return self._parse_chat_response(result, kwargs)
        except Exception as e:
            self._raise_safe_error("千问聊天完成请求失败", e)

    def text_completion(self, prompt, **kwargs):
        """生成文本完成内容"""
        messages = [{'role': 'user', 'content': prompt}]
        return self.chat_completion(messages, **kwargs)

    def embedding(self, text, **kwargs):
        """生成文本嵌入向量（兼容OpenAI格式）"""
        url = self._join_url('/embeddings')
        headers = self._request_headers()

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
            self._raise_safe_error("阿里千问嵌入向量请求失败", e)


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
        url = self._join_url('/chat/completions')
        headers = self._request_headers()
        if self.organization:
            headers['OpenAI-Organization'] = self.organization

        data = {
            'model': self.model_config.get('chat', 'deepseek-chat'),
            'messages': messages,
            'temperature': kwargs.get('temperature', self.model_config.get('temperature', 0.7)),
            'max_tokens': kwargs.get('max_tokens', self.model_config.get('max_tokens', 2000)),
        }
        data.update(kwargs)

        original_timeout = self.timeout
        self.timeout = 30

        try:
            response = self._make_request(
                'POST', url, headers=headers, json=data)
            result = response.json()
            return self._parse_chat_response(result, kwargs)
        except Exception as e:
            self._raise_safe_error("DeepSeek聊天完成请求失败", e)
        finally:
            self.timeout = original_timeout

    def text_completion(self, prompt, **kwargs):
        """生成文本完成内容"""
        messages = [{'role': 'user', 'content': prompt}]
        return self.chat_completion(messages, **kwargs)

    def embedding(self, text, **kwargs):
        """生成文本嵌入向量"""
        url = self._join_url('/embeddings')
        headers = self._request_headers()
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
            self._raise_safe_error("DeepSeek嵌入向量请求失败", e)


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
        url = self._join_url('/chat/completions')
        headers = self._request_headers()
        if self.app_key:
            headers['X-AppKey'] = self.app_key

        data = {
            'model': self.model_config.get('chat', 'doubao-pro'),
            'messages': messages,
            'temperature': kwargs.get('temperature', self.model_config.get('temperature', 0.7)),
            'max_tokens': kwargs.get('max_tokens', self.model_config.get('max_tokens', 2000)),
        }
        data.update(kwargs)

        try:
            response = self._make_request(
                'POST', url, headers=headers, json=data)
            result = response.json()
            return self._parse_chat_response(result, kwargs)
        except Exception as e:
            self._raise_safe_error("豆包聊天完成请求失败", e)

    def text_completion(self, prompt, **kwargs):
        """生成文本完成内容"""
        messages = [{'role': 'user', 'content': prompt}]
        return self.chat_completion(messages, **kwargs)

    def embedding(self, text, **kwargs):
        """生成文本嵌入向量"""
        url = self._join_url('/embeddings')
        headers = self._request_headers()
        if self.app_key:
            headers['X-AppKey'] = self.app_key

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
            self._raise_safe_error("豆包嵌入向量请求失败", e)


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
            self._raise_safe_error("获取文心一言Access Token失败", e)

    def chat_completion(self, messages, **kwargs):
        """生成聊天完成内容"""
        if not self.access_token:
            raise AIClientError("文心一言Access Token未配置")

        url = f"{self.base_url}/wenxinworkshop/chat/eb-instant"
        headers = {
            'Content-Type': 'application/json',
        }

        prompt = self._convert_messages_to_prompt(messages)

        data = {
            'messages': [
                {
                    'role': 'user',
                    'content': prompt
                }
            ],
            'temperature': kwargs.get('temperature', self.model_config.get('temperature', 0.7)),
            'max_tokens': kwargs.get('max_tokens', self.model_config.get('max_tokens', 1024)),
        }
        data.update(kwargs)

        url_with_token = f"{url}?access_token={self.access_token}"

        try:
            response = self._make_request(
                'POST', url_with_token, headers=headers, json=data)
            result = response.json()
            content = result.get('result', '')
            return content
        except Exception as e:
            self._raise_safe_error("文心一言聊天完成请求失败", e)

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

        url_with_token = f"{url}?access_token={self.access_token}"

        try:
            response = self._make_request(
                'POST', url_with_token, headers=headers, json=data)
            result = response.json()
            return result.get('data', [{}])[0].get('embedding', [])
        except Exception as e:
            self._raise_safe_error("文心一言嵌入向量请求失败", e)


class LocalModelClient(BaseAIClient):
    """本地大模型客户端实现"""

    def __init__(self, base_url=None, api_key=None, model_config=None):
        super().__init__(
            provider='local',
            base_url=base_url,
            api_key=api_key,
            model_config=model_config)
        self.local_config = {}

    def chat_completion(self, messages, **kwargs):
        """生成聊天完成内容"""
        url = self._join_url('/chat/completions')
        headers = self._request_headers()

        data = {
            'model': self.model_config.get(
                'chat',
                'local-model'),
            'messages': messages,
            'temperature': kwargs.get(
                'temperature',
                self.model_config.get('temperature', 0.7)),
            'max_tokens': kwargs.get(
                'max_tokens',
                self.model_config.get('max_tokens', 4096)),
        }
        data.update(kwargs)

        try:
            response = self._make_request(
                'POST', url, headers=headers, json=data)
            result = response.json()
            return self._parse_chat_response(result, kwargs)
        except Exception as e:
            self._raise_safe_error("本地大模型聊天完成请求失败", e)

    def text_completion(self, prompt, **kwargs):
        """生成文本完成内容"""
        messages = [{'role': 'user', 'content': prompt}]
        return self.chat_completion(messages, **kwargs)

    def embedding(self, text, **kwargs):
        """生成文本嵌入向量"""
        url = self._join_url('/embeddings')
        headers = self._request_headers()

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
            self._raise_safe_error("本地大模型嵌入向量请求失败", e)


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
            return message.get('content', '') or ""
        except Exception as e:
            self._raise_safe_error("Ollama聊天完成请求失败", e)

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
            self._raise_safe_error("Ollama嵌入向量请求失败", e)


class AzureOpenAIClient(OpenAIClient):
    """Azure OpenAI客户端实现"""

    def __init__(self, base_url=None, api_key=None, model_config=None):
        super().__init__(base_url=base_url, api_key=api_key, model_config=model_config)
        self.provider = 'azure'
        self.api_version = self.provider_specific_config.get(
            'api_version', '2024-02-15-preview')

    def _ensure_client(self):
        if self.client is not None:
            return True
        if self._openai is None:
            try:
                import openai
                self._openai = openai
            except ImportError:
                return False
        if not self.api_key or not self.base_url:
            return False
        try:
            self.client = self._openai.AzureOpenAI(
                api_key=self.api_key,
                azure_endpoint=self.base_url,
                api_version=self.api_version)
            return True
        except Exception as e:
            logger.error(f"创建Azure OpenAI客户端失败: {str(e)}")
            return False

    def _rest_url(self, path: str) -> str:
        if not self.base_url:
            raise AIClientError("Azure OpenAI API基础URL未配置")
        deployment = self.model_config.get('chat') or self.model_config.get('model_name')
        if not deployment:
            raise AIClientError("Azure OpenAI部署名称未配置")
        base = self.base_url.rstrip('/')
        if '/openai/deployments/' in base:
            endpoint = self._join_url(path, base)
        else:
            endpoint = f"{base}/openai/deployments/{deployment}{path}"
        separator = '&' if '?' in endpoint else '?'
        if 'api-version=' not in endpoint:
            endpoint = f"{endpoint}{separator}api-version={self.api_version}"
        return endpoint

    def _request_headers(self):
        return {
            'api-key': self.api_key,
            'Content-Type': 'application/json',
        }


class AnthropicClient(BaseAIClient):
    """Anthropic Claude客户端实现"""

    def __init__(self, base_url=None, api_key=None, model_config=None):
        if not base_url:
            base_url = 'https://api.anthropic.com/v1'
        super().__init__(
            provider='anthropic',
            base_url=base_url,
            api_key=api_key,
            model_config=model_config)
        self.anthropic_version = self.provider_specific_config.get(
            'anthropic_version', '2023-06-01')

    def chat_completion(self, messages, **kwargs):
        if not self.api_key:
            raise AIClientError("Anthropic API Key未配置")
        url = self._join_url('/messages')
        headers = {
            'x-api-key': self.api_key,
            'anthropic-version': self.anthropic_version,
            'Content-Type': 'application/json',
        }
        system_prompt = None
        anthropic_messages = []
        for message in messages:
            role = message.get('role')
            content = message.get('content', '')
            if role == 'system':
                system_prompt = content if system_prompt is None else f"{system_prompt}\n{content}"
            elif role in ['user', 'assistant']:
                anthropic_messages.append({'role': role, 'content': content})
        data = {
            'model': self.model_config.get('chat', 'claude-3-haiku-20240307'),
            'messages': anthropic_messages or [{'role': 'user', 'content': ''}],
            'temperature': kwargs.get('temperature', self.model_config.get('temperature', 0.7)),
            'max_tokens': kwargs.get('max_tokens', self.model_config.get('max_tokens', 2000)),
        }
        if system_prompt:
            data['system'] = system_prompt
        if 'top_p' in kwargs or self.model_config.get('top_p') is not None:
            data['top_p'] = kwargs.get('top_p', self.model_config.get('top_p', 1.0))
        try:
            response = self._make_request('POST', url, headers=headers, json=data)
            result = response.json()
            contents = result.get('content') or []
            for item in contents:
                if item.get('type') == 'text':
                    return item.get('text', '')
            return ''
        except Exception as e:
            self._raise_safe_error("Anthropic聊天完成请求失败", e)

    def text_completion(self, prompt, **kwargs):
        messages = [{'role': 'user', 'content': prompt}]
        return self.chat_completion(messages, **kwargs)

    def embedding(self, text, **kwargs):
        raise AIClientError("Anthropic暂不支持嵌入向量接口")


class GoogleGeminiClient(BaseAIClient):
    """Google Gemini客户端实现"""

    def __init__(self, base_url=None, api_key=None, model_config=None):
        if not base_url:
            base_url = 'https://generativelanguage.googleapis.com/v1beta'
        super().__init__(
            provider='google',
            base_url=base_url,
            api_key=api_key,
            model_config=model_config)

    def _convert_messages(self, messages):
        contents = []
        system_parts = []
        for message in messages:
            role = message.get('role')
            content = message.get('content', '')
            if role == 'system':
                system_parts.append({'text': content})
            else:
                contents.append({
                    'role': 'model' if role == 'assistant' else 'user',
                    'parts': [{'text': content}]
                })
        return contents or [{'role': 'user', 'parts': [{'text': ''}]}], system_parts

    def chat_completion(self, messages, **kwargs):
        if not self.api_key:
            raise AIClientError("Google Gemini API Key未配置")
        model = self.model_config.get('chat', 'gemini-1.5-flash')
        base = self.base_url.rstrip('/')
        if ':generateContent' in base:
            safe_url = base
        elif '/models/' in base:
            safe_url = f"{base}:generateContent"
        else:
            safe_url = f"{base}/models/{model}:generateContent"
        headers = {
            'Content-Type': 'application/json',
            'x-goog-api-key': self.api_key,
        }
        contents, system_parts = self._convert_messages(messages)
        data = {
            'contents': contents,
            'generationConfig': {
                'temperature': kwargs.get('temperature', self.model_config.get('temperature', 0.7)),
                'maxOutputTokens': kwargs.get('max_tokens', self.model_config.get('max_tokens', 2000)),
                'topP': kwargs.get('top_p', self.model_config.get('top_p', 1.0)),
            }
        }
        if system_parts:
            data['systemInstruction'] = {'parts': system_parts}
        try:
            response = self._make_request('POST', safe_url, headers=headers, json=data)
            result = response.json()
            candidates = result.get('candidates') or []
            if not candidates:
                return ''
            parts = candidates[0].get('content', {}).get('parts') or []
            return ''.join(part.get('text', '') for part in parts)
        except Exception as e:
            self._raise_safe_error("Google Gemini聊天完成请求失败", e)

    def text_completion(self, prompt, **kwargs):
        messages = [{'role': 'user', 'content': prompt}]
        return self.chat_completion(messages, **kwargs)

    def embedding(self, text, **kwargs):
        if not self.api_key:
            raise AIClientError("Google Gemini API Key未配置")
        model = kwargs.get(
            'model',
            self.model_config.get('embedding', self.model_config.get('chat', 'text-embedding-004')))
        base = self.base_url.rstrip('/')
        if ':embedContent' in base:
            safe_url = base
        elif '/models/' in base:
            safe_url = f"{base}:embedContent"
        else:
            safe_url = f"{base}/models/{model}:embedContent"
        headers = {
            'Content-Type': 'application/json',
            'x-goog-api-key': self.api_key,
        }
        data = {'content': {'parts': [{'text': text}]}}
        try:
            response = self._make_request('POST', safe_url, headers=headers, json=data)
            result = response.json()
            return result.get('embedding', {}).get('values', [])
        except Exception as e:
            self._raise_safe_error("Google Gemini嵌入向量请求失败", e)


class TencentHunyuanClient(BaseAIClient):
    """腾讯混元OpenAI兼容客户端实现"""

    def __init__(self, base_url=None, api_key=None, model_config=None):
        if not base_url:
            base_url = 'https://api.hunyuan.cloud.tencent.com/v1'
        super().__init__(
            provider='tencent',
            base_url=base_url,
            api_key=api_key,
            model_config=model_config)

    def chat_completion(self, messages, **kwargs):
        url = self._join_url('/chat/completions')
        headers = self._request_headers()
        data = {
            'model': self.model_config.get('chat', 'hunyuan-lite'),
            'messages': messages,
            'temperature': kwargs.get('temperature', self.model_config.get('temperature', 0.7)),
            'max_tokens': kwargs.get('max_tokens', self.model_config.get('max_tokens', 2000)),
        }
        if 'top_p' in kwargs or self.model_config.get('top_p') is not None:
            data['top_p'] = kwargs.get('top_p', self.model_config.get('top_p', 1.0))
        try:
            response = self._make_request('POST', url, headers=headers, json=data)
            result = response.json()
            return self._parse_chat_response(result, kwargs)
        except Exception as e:
            self._raise_safe_error("腾讯混元聊天完成请求失败", e)

    def text_completion(self, prompt, **kwargs):
        messages = [{'role': 'user', 'content': prompt}]
        return self.chat_completion(messages, **kwargs)

    def embedding(self, text, **kwargs):
        url = self._join_url('/embeddings')
        headers = self._request_headers()
        data = {
            'model': self.model_config.get('embedding', self.model_config.get('chat', 'hunyuan-embedding')),
            'input': text
        }
        try:
            response = self._make_request('POST', url, headers=headers, json=data)
            result = response.json()
            return result.get('data', [{}])[0].get('embedding', [])
        except Exception as e:
            self._raise_safe_error("腾讯混元嵌入向量请求失败", e)


class AIClient:
    """AI模型客户端入口类"""

    def __init__(self, model_config_id=None, provider=None):
        if model_config_id:
            try:
                self.model_config = AIModelConfig.objects.get(
                    id=model_config_id, is_active=True)
                self.provider = self.model_config.provider or provider or 'openai'
            except AIModelConfig.DoesNotExist:
                logger.error(f"AI模型配置不存在或未启用: {model_config_id}")
                raise AIClientError("AI模型配置不存在或未启用，请检查模型配置后重试") from None
        else:
            self.provider = provider or 'openai'
            self.model_config = None

        self.client = self._create_client()

    def _create_client(self):
        """创建 OpenAI 兼容客户端实例 — 全站统一。"""
        if hasattr(self.model_config, 'api_base'):
            base_url = self.model_config.base_url
            api_key = self.model_config.api_key
            model_name = self.model_config.primary_model_name()
        elif isinstance(self.model_config, dict):
            base_url = AIModelConfig.normalize_api_base(
                self.model_config.get('api_base') or self.model_config.get('base_url')
            )
            api_key = self.model_config.get('api_key')
            model_name = self.model_config.get('model_name') or 'gpt-4o-mini'
        else:
            base_url = None
            api_key = None
            model_name = 'gpt-4o-mini'

        model_config = {
            'chat': model_name,
            'model_name': model_name,
            'temperature': 0.7,
            'max_tokens': 2000,
            'top_p': 1.0,
        }

        client = OpenAIClient(
            base_url=base_url,
            api_key=api_key,
            model_config=model_config)

        if self.model_config:
            self._apply_model_config_to_client(client)

        return client

    def _apply_model_config_to_client(self, client):
        """将模型配置应用到客户端实例 — 全站 OpenAI 兼容。"""
        if not self.model_config:
            return

        if hasattr(self.model_config, 'api_base') and self.model_config.api_base:
            client.base_url = self.model_config.base_url
            client.api_base = client.base_url

        if hasattr(self.model_config, 'api_key') and self.model_config.api_key:
            client.api_key = self.model_config.api_key

        if hasattr(self.model_config, 'primary_model_name'):
            model_name = self.model_config.primary_model_name()
        else:
            model_name = self.model_config.get('model_name', 'gpt-4o-mini') if isinstance(self.model_config, dict) else 'gpt-4o-mini'
        client.model_config['chat'] = model_name
        client.model_config['model_name'] = model_name

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
        """从配置字典创建 AIClient 实例 — 全站 OpenAI 兼容。"""
        if not config:
            raise AIClientError("配置不能为空")

        api_key = config.get('api_key')
        base_url = AIModelConfig.normalize_api_base(config.get('base_url') or config.get('api_base'))
        return OpenAIClient(base_url=base_url, api_key=api_key, model_config=config)
