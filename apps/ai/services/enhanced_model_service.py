"""
增强型AI模型集成服务
整合Dify和扣子的多模型管理能力
"""

import json
import logging
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod
from datetime import datetime
import httpx


from apps.ai.models import AIModelConfig

logger = logging.getLogger(__name__)


class ModelProvider(Enum):
    """模型提供商"""
    OPENAI = "openai"
    AZURE = "azure"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    BAIDU = "baidu"
    ALIBABA = "alibaba"
    TENCENT = "tencent"
    DEEPSEEK = "deepseek"
    DOUBAO = "doubao"
    LOCAL = "local"


class ModelCapability(Enum):
    """模型能力"""
    CHAT = "chat"
    TEXT_GENERATION = "text_generation"
    TEXT_EMBEDDING = "text_embedding"
    IMAGE_GENERATION = "image_generation"
    IMAGE_UNDERSTANDING = "image_understanding"
    AUDIO_TO_TEXT = "audio_to_text"
    TEXT_TO_AUDIO = "text_to_audio"


@dataclass
class ModelInfo:
    """模型信息"""
    provider: ModelProvider
    model_id: str
    model_name: str
    capabilities: List[ModelCapability]
    max_tokens: int = 4096
    context_window: int = 8192
    pricing: Dict[str, float] = field(default_factory=dict)
    is_available: bool = True


@dataclass
class ModelResponse:
    """模型响应"""
    success: bool
    content: Optional[str] = None
    usage: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    latency: float = 0.0
    provider: Optional[ModelProvider] = None
    model_id: Optional[str] = None


class BaseModelAdapter(ABC):
    """模型适配器基类"""

    def __init__(self, config: AIModelConfig):
        self.config = config

    @abstractmethod
    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        **kwargs
    ) -> ModelResponse:
        """聊天完成"""

    @abstractmethod
    async def text_generation(
        self,
        prompt: str,
        **kwargs
    ) -> ModelResponse:
        """文本生成"""

    @abstractmethod
    async def embedding(
        self,
        texts: List[str],
        **kwargs
    ) -> ModelResponse:
        """文本嵌入"""

    def _build_error_response(self, error: str) -> ModelResponse:
        """构建错误响应"""
        return ModelResponse(
            success=False,
            error=error
        )


class OpenAIAdapter(BaseModelAdapter):
    """OpenAI模型适配器"""

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = None,
        **kwargs
    ) -> ModelResponse:
        """OpenAI聊天完成"""
        start_time = datetime.now()

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                headers = {
                    "Authorization": f"Bearer {self.config.api_key}",
                    "Content-Type": "application/json"
                }

                payload = {
                    "model": self.config.model_name,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens or self.config.max_tokens,
                    "top_p": self.config.top_p
                }

                if kwargs.get('stream'):
                    payload["stream"] = True

                response = await client.post(
                    f"{self.config.api_base}/chat/completions",
                    headers=headers,
                    json=payload
                )

                response.raise_for_status()
                data = response.json()

                content = data["choices"][0]["message"]["content"]
                usage = data.get("usage", {})

                latency = (datetime.now() - start_time).total_seconds()

                return ModelResponse(
                    success=True,
                    content=content,
                    usage={
                        "prompt_tokens": usage.get("prompt_tokens", 0),
                        "completion_tokens": usage.get("completion_tokens", 0),
                        "total_tokens": usage.get("total_tokens", 0)
                    },
                    latency=latency,
                    provider=ModelProvider.OPENAI,
                    model_id=self.config.model_name
                )

        except Exception as e:
            logger.error(f"OpenAI API调用失败: {e}")
            return self._build_error_response(str(e))

    async def text_generation(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = None,
        **kwargs
    ) -> ModelResponse:
        """OpenAI文本生成"""
        messages = [{"role": "user", "content": prompt}]
        return await self.chat_completion(messages, temperature, max_tokens, **kwargs)

    async def embedding(
        self,
        texts: List[str],
        **kwargs
    ) -> ModelResponse:
        """OpenAI文本嵌入"""
        start_time = datetime.now()

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                headers = {
                    "Authorization": f"Bearer {self.config.api_key}",
                    "Content-Type": "application/json"
                }

                payload = {
                    "model": "text-embedding-3-small",
                    "input": texts
                }

                response = await client.post(
                    f"{self.config.api_base}/embeddings",
                    headers=headers,
                    json=payload
                )

                response.raise_for_status()
                data = response.json()

                embeddings = [item["embedding"] for item in data["data"]]
                usage = data.get("usage", {})

                latency = (datetime.now() - start_time).total_seconds()

                return ModelResponse(
                    success=True,
                    content=json.dumps(embeddings),
                    usage={
                        "prompt_tokens": usage.get("prompt_tokens", 0),
                        "total_tokens": usage.get("total_tokens", 0)
                    },
                    latency=latency,
                    provider=ModelProvider.OPENAI,
                    model_id="text-embedding-3-small"
                )

        except Exception as e:
            logger.error(f"OpenAI Embedding API调用失败: {e}")
            return self._build_error_response(str(e))


class AnthropicAdapter(BaseModelAdapter):
    """Anthropic模型适配器"""

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = None,
        **kwargs
    ) -> ModelResponse:
        """Anthropic聊天完成"""
        start_time = datetime.now()

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                headers = {
                    "x-api-key": self.config.api_key,
                    "Content-Type": "application/json",
                    "anthropic-version": "2023-06-01"
                }

                system_message = None
                user_messages = []

                for msg in messages:
                    if msg["role"] == "system":
                        system_message = msg["content"]
                    else:
                        user_messages.append(msg)

                payload = {
                    "model": self.config.model_name,
                    "messages": user_messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens or self.config.max_tokens
                }

                if system_message:
                    payload["system"] = system_message

                response = await client.post(
                    f"{self.config.api_base}/messages",
                    headers=headers,
                    json=payload
                )

                response.raise_for_status()
                data = response.json()

                content = data["content"][0]["text"]
                usage = data.get("usage", {})

                latency = (datetime.now() - start_time).total_seconds()

                return ModelResponse(
                    success=True,
                    content=content,
                    usage={
                        "input_tokens": usage.get("input_tokens", 0),
                        "output_tokens": usage.get("output_tokens", 0)
                    },
                    latency=latency,
                    provider=ModelProvider.ANTHROPIC,
                    model_id=self.config.model_name
                )

        except Exception as e:
            logger.error(f"Anthropic API调用失败: {e}")
            return self._build_error_response(str(e))

    async def text_generation(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = None,
        **kwargs
    ) -> ModelResponse:
        """Anthropic文本生成"""
        messages = [{"role": "user", "content": prompt}]
        return await self.chat_completion(messages, temperature, max_tokens, **kwargs)

    async def embedding(
        self,
        texts: List[str],
        **kwargs
    ) -> ModelResponse:
        """Anthropic不支持嵌入"""
        return self._build_error_response("Anthropic模型不支持文本嵌入")


class DeepSeekAdapter(BaseModelAdapter):
    """DeepSeek模型适配器"""

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = None,
        **kwargs
    ) -> ModelResponse:
        """DeepSeek聊天完成"""
        start_time = datetime.now()

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                headers = {
                    "Authorization": f"Bearer {self.config.api_key}",
                    "Content-Type": "application/json"
                }

                payload = {
                    "model": self.config.model_name,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens or self.config.max_tokens
                }

                response = await client.post(
                    f"{self.config.api_base}/chat/completions",
                    headers=headers,
                    json=payload
                )

                response.raise_for_status()
                data = response.json()

                content = data["choices"][0]["message"]["content"]
                usage = data.get("usage", {})

                latency = (datetime.now() - start_time).total_seconds()

                return ModelResponse(
                    success=True,
                    content=content,
                    usage={
                        "prompt_tokens": usage.get("prompt_tokens", 0),
                        "completion_tokens": usage.get("completion_tokens", 0),
                        "total_tokens": usage.get("total_tokens", 0)
                    },
                    latency=latency,
                    provider=ModelProvider.DEEPSEEK,
                    model_id=self.config.model_name
                )

        except Exception as e:
            logger.error(f"DeepSeek API调用失败: {e}")
            return self._build_error_response(str(e))

    async def text_generation(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = None,
        **kwargs
    ) -> ModelResponse:
        """DeepSeek文本生成"""
        messages = [{"role": "user", "content": prompt}]
        return await self.chat_completion(messages, temperature, max_tokens, **kwargs)

    async def embedding(
        self,
        texts: List[str],
        **kwargs
    ) -> ModelResponse:
        """DeepSeek文本嵌入"""
        start_time = datetime.now()

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                headers = {
                    "Authorization": f"Bearer {self.config.api_key}",
                    "Content-Type": "application/json"
                }

                payload = {
                    "model": "deepseek-embed",
                    "input": texts
                }

                response = await client.post(
                    f"{self.config.api_base}/embeddings",
                    headers=headers,
                    json=payload
                )

                response.raise_for_status()
                data = response.json()

                embeddings = [item["embedding"] for item in data["data"]]

                latency = (datetime.now() - start_time).total_seconds()

                return ModelResponse(
                    success=True,
                    content=json.dumps(embeddings),
                    latency=latency,
                    provider=ModelProvider.DEEPSEEK,
                    model_id="deepseek-embed"
                )

        except Exception as e:
            logger.error(f"DeepSeek Embedding API调用失败: {e}")
            return self._build_error_response(str(e))


class EnhancedModelService:
    """增强型模型服务"""

    def __init__(self):
        self.adapters: Dict[str, BaseModelAdapter] = {}
        self.model_cache: Dict[str, ModelInfo] = {}
        self._init_model_cache()

    def _init_model_cache(self):
        """初始化模型缓存"""
        self.model_cache = {"gpt-4": ModelInfo(provider=ModelProvider.OPENAI,
                                               model_id="gpt-4",
                                               model_name="GPT-4",
                                               capabilities=[ModelCapability.CHAT,
                                                             ModelCapability.TEXT_GENERATION],
                                               max_tokens=8192,
                                               context_window=32768,
                                               pricing={"input": 0.03,
                                                        "output": 0.06}),
                            "gpt-4-turbo": ModelInfo(provider=ModelProvider.OPENAI,
                                                     model_id="gpt-4-turbo",
                                                     model_name="GPT-4 Turbo",
                                                     capabilities=[ModelCapability.CHAT,
                                                                   ModelCapability.TEXT_GENERATION],
                                                     max_tokens=4096,
                                                     context_window=128000,
                                                     pricing={"input": 0.01,
                                                              "output": 0.03}),
                            "gpt-3.5-turbo": ModelInfo(provider=ModelProvider.OPENAI,
                                                       model_id="gpt-3.5-turbo",
                                                       model_name="GPT-3.5 Turbo",
                                                       capabilities=[ModelCapability.CHAT,
                                                                     ModelCapability.TEXT_GENERATION],
                                                       max_tokens=4096,
                                                       context_window=16385,
                                                       pricing={"input": 0.0005,
                                                                "output": 0.0015}),
                            "claude-3-5-sonnet-20241022": ModelInfo(provider=ModelProvider.ANTHROPIC,
                                                                    model_id="claude-3-5-sonnet-20241022",
                                                                    model_name="Claude 3.5 Sonnet",
                                                                    capabilities=[ModelCapability.CHAT,
                                                                                  ModelCapability.TEXT_GENERATION],
                                                                    max_tokens=8192,
                                                                    context_window=200000,
                                                                    pricing={"input": 0.003,
                                                                             "output": 0.015}),
                            "deepseek-chat": ModelInfo(provider=ModelProvider.DEEPSEEK,
                                                       model_id="deepseek-chat",
                                                       model_name="DeepSeek Chat",
                                                       capabilities=[ModelCapability.CHAT,
                                                                     ModelCapability.TEXT_GENERATION],
                                                       max_tokens=4096,
                                                       context_window=32768,
                                                       pricing={"input": 0.00014,
                                                                "output": 0.00028}),
                            "deepseek-reasoner": ModelInfo(provider=ModelProvider.DEEPSEEK,
                                                           model_id="deepseek-reasoner",
                                                           model_name="DeepSeek Reasoner",
                                                           capabilities=[ModelCapability.CHAT,
                                                                         ModelCapability.TEXT_GENERATION],
                                                           max_tokens=4096,
                                                           context_window=32768,
                                                           pricing={"input": 0.00055,
                                                                    "output": 0.00219})}

    def get_adapter(self, config_id: int) -> Optional[BaseModelAdapter]:
        """获取模型适配器"""
        if str(config_id) in self.adapters:
            return self.adapters[str(config_id)]

        try:
            config = AIModelConfig.objects.get(id=config_id, is_active=True)

            adapter_class = self._get_adapter_class(config.provider)
            adapter = adapter_class(config)

            self.adapters[str(config_id)] = adapter
            return adapter

        except AIModelConfig.DoesNotExist:
            logger.error(f"模型配置不存在: {config_id}")
            return None

    def _get_adapter_class(self, provider: str):
        """获取适配器类"""
        adapter_map = {
            "openai": OpenAIAdapter,
            "azure": OpenAIAdapter,
            "anthropic": AnthropicAdapter,
            "deepseek": DeepSeekAdapter,
        }
        return adapter_map.get(provider, OpenAIAdapter)

    async def chat_completion(
        self,
        config_id: int,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = None,
        **kwargs
    ) -> ModelResponse:
        """聊天完成"""
        adapter = self.get_adapter(config_id)
        if not adapter:
            return ModelResponse(success=False, error="模型配置不存在或已禁用")

        return await adapter.chat_completion(messages, temperature, max_tokens, **kwargs)

    async def text_generation(
        self,
        config_id: int,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = None,
        **kwargs
    ) -> ModelResponse:
        """文本生成"""
        adapter = self.get_adapter(config_id)
        if not adapter:
            return ModelResponse(success=False, error="模型配置不存在或已禁用")

        return await adapter.text_generation(prompt, temperature, max_tokens, **kwargs)

    async def embedding(
        self,
        config_id: int,
        texts: List[str],
        **kwargs
    ) -> ModelResponse:
        """文本嵌入"""
        adapter = self.get_adapter(config_id)
        if not adapter:
            return ModelResponse(success=False, error="模型配置不存在或已禁用")

        return await adapter.embedding(texts, **kwargs)

    def get_available_models(self) -> List[Dict[str, Any]]:
        """获取可用模型列表"""
        return [
            {
                "id": model_id,
                "name": info.model_name,
                "provider": info.provider.value,
                "capabilities": [c.value for c in info.capabilities],
                "max_tokens": info.max_tokens,
                "context_window": info.context_window,
                "pricing": info.pricing,
                "is_available": info.is_available
            }
            for model_id, info in self.model_cache.items()
        ]

    def get_model_info(self, model_id: str) -> Optional[Dict[str, Any]]:
        """获取模型信息"""
        info = self.model_cache.get(model_id)
        if not info:
            return None

        return {
            "id": info.model_id,
            "name": info.model_name,
            "provider": info.provider.value,
            "capabilities": [c.value for c in info.capabilities],
            "max_tokens": info.max_tokens,
            "context_window": info.context_window,
            "pricing": info.pricing
        }

    async def stream_completion(
        self,
        config_id: int,
        messages: List[Dict[str, str]],
        on_chunk: Callable[[str], None],
        temperature: float = 0.7,
        max_tokens: int = None,
        **kwargs
    ):
        """流式完成"""
        adapter = self.get_adapter(config_id)
        if not adapter:
            raise ValueError("模型配置不存在或已禁用")

        if not hasattr(adapter, 'stream_chat_completion'):
            raise ValueError("该模型不支持流式输出")

        async for chunk in adapter.stream_chat_completion(messages, temperature, max_tokens, **kwargs):
            on_chunk(chunk)

    def clear_cache(self, config_id: Optional[int] = None):
        """清除缓存"""
        if config_id:
            self.adapters.pop(str(config_id), None)
        else:
            self.adapters.clear()


model_service = EnhancedModelService()
