"""
增强型节点处理器
整合Dify和扣子的核心节点能力
"""

import json
import re
import ast
import logging
from typing import Dict, Any, List, Optional
from abc import ABC, abstractmethod
import asyncio

from apps.ai.processors.base_processor import BaseNodeProcessor, NodeProcessorRegistry
from apps.ai.services.ai_analysis_service import AIAnalysisService

logger = logging.getLogger(__name__)


class KnowledgeRetrievalProcessor(BaseNodeProcessor):
    """知识库检索节点处理器（整合Dify的RAG能力）"""
    
    def __init__(self, node_type_code: str):
        super().__init__(node_type_code)
        self.ai_service = AIAnalysisService()
    
    def _get_config_schema(self) -> Dict[str, Any]:
        return {
            'knowledge_base_id': {
                'type': 'string',
                'required': True,
                'label': '知识库',
                'description': '选择要检索的知识库',
                'placeholder': '请选择知识库'
            },
            'query_variable': {
                'type': 'string',
                'required': True,
                'label': '查询变量',
                'description': '输入查询内容的变量名',
                'placeholder': '例如: input_text'
            },
            'retrieval_mode': {
                'type': 'string',
                'required': False,
                'label': '检索模式',
                'default': 'semantic',
                'options': [
                    {'value': 'semantic', 'label': '语义检索'},
                    {'value': 'keyword', 'label': '关键词检索'},
                    {'value': 'hybrid', 'label': '混合检索'}
                ]
            },
            'top_k': {
                'type': 'number',
                'required': False,
                'label': '返回数量',
                'default': 5,
                'min': 1,
                'max': 20
            },
            'similarity_threshold': {
                'type': 'number',
                'required': False,
                'label': '相似度阈值',
                'default': 0.7,
                'min': 0.0,
                'max': 1.0
            },
            'output_mode': {
                'type': 'string',
                'required': False,
                'label': '输出模式',
                'default': 'content',
                'options': [
                    {'value': 'content', 'label': '仅内容'},
                    {'value': 'with_score', 'label': '含相似度'},
                    {'value': 'full', 'label': '完整信息'}
                ]
            }
        }
    
    async def execute_async(self, config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """异步执行知识检索"""
        output = {}
        
        try:
            knowledge_base_id = config.get('knowledge_base_id')
            query_variable = config.get('query_variable')
            query_text = context.get(query_variable, '')
            retrieval_mode = config.get('retrieval_mode', 'semantic')
            top_k = config.get('top_k', 5)
            similarity_threshold = config.get('similarity_threshold', 0.7)
            output_mode = config.get('output_mode', 'content')
            
            if not query_text:
                output['retrieval_success'] = True
                output['documents'] = []
                output['message'] = '查询内容为空'
                return output
            
            from apps.ai.models import AIKnowledgeItem, AIKnowledgeVector
            
            if retrieval_mode == 'semantic':
                from apps.ai.utils.embedding_service import embedding_service
                query_vector = embedding_service.get_embedding(query_text)
                
                vectors = AIKnowledgeVector.objects.filter(
                    knowledge_item__knowledge_base_id=knowledge_base_id,
                    knowledge_item__status='published'
                )
                
                results = []
                for vec in vectors:
                    similarity = embedding_service.cosine_similarity(query_vector, vec.vector)
                    if similarity >= similarity_threshold:
                        results.append({
                            'item_id': str(vec.knowledge_item.id),
                            'title': vec.knowledge_item.title,
                            'content': vec.knowledge_item.content[:500],
                            'similarity': similarity
                        })
                
                results.sort(key=lambda x: x['similarity'], reverse=True)
                results = results[:top_k]
                
            else:
                from django.db.models import Q
                items = AIKnowledgeItem.objects.filter(
                    knowledge_base_id=knowledge_base_id,
                    status='published'
                ).filter(
                    Q(title__icontains=query_text) | 
                    Q(content__icontains=query_text)
                )[:top_k]
                
                results = []
                for item in items:
                    results.append({
                        'item_id': str(item.id),
                        'title': item.title,
                        'content': item.content[:500],
                        'similarity': 1.0
                    })
            
            if output_mode == 'content':
                output['documents'] = [r['content'] for r in results]
                output['document_count'] = len(results)
            elif output_mode == 'with_score':
                output['documents'] = results
                output['document_count'] = len(results)
            else:
                output['documents'] = results
                output['document_count'] = len(results)
                output['retrieved_from'] = knowledge_base_id
                output['query'] = query_text
            
            output['retrieval_success'] = True
            
        except Exception as e:
            logger.error(f"知识检索失败: {e}")
            output['retrieval_success'] = False
            output['error_message'] = str(e)
        
        return output
    
    def execute(self, config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """同步执行（兼容旧接口）"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(self.execute_async(config, context))
        finally:
            loop.close()


class IntentRecognitionProcessor(BaseNodeProcessor):
    """意图识别节点处理器（整合扣子的NLU能力）"""
    
    def __init__(self, node_type_code: str):
        super().__init__(node_type_code)
        self.ai_service = AIAnalysisService()
    
    def _get_config_schema(self) -> Dict[str, Any]:
        return {
            'input_variable': {
                'type': 'string',
                'required': True,
                'label': '输入变量',
                'description': '输入文本的变量名',
                'placeholder': '例如: user_input'
            },
            'intents': {
                'type': 'array',
                'required': True,
                'label': '意图定义',
                'description': '定义要识别的意图列表',
                'items': {
                    'type': 'object',
                    'properties': {
                        'intent_id': {'type': 'string', 'label': '意图ID'},
                        'intent_name': {'type': 'string', 'label': '意图名称'},
                        'examples': {'type': 'array', 'label': '示例句子'},
                        'keywords': {'type': 'array', 'label': '关键词'}
                    }
                }
            },
            'output_intent_variable': {
                'type': 'string',
                'required': False,
                'label': '意图输出变量',
                'default': 'recognized_intent'
            },
            'output_confidence_variable': {
                'type': 'string',
                'required': False,
                'label': '置信度输出变量',
                'default': 'intent_confidence'
            },
            'use_llm': {
                'type': 'boolean',
                'required': False,
                'label': '使用LLM识别',
                'default': True,
                'description': '使用大语言模型进行意图识别'
            },
            'model_name': {
                'type': 'string',
                'required': False,
                'label': '模型名称',
                'default': 'gpt-3.5-turbo'
            }
        }
    
    async def execute_async(self, config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """异步执行意图识别"""
        output = {}
        
        try:
            input_variable = config.get('input_variable')
            input_text = context.get(input_variable, '')
            intents = config.get('intents', [])
            output_intent_var = config.get('output_intent_variable', 'recognized_intent')
            output_confidence_var = config.get('output_confidence_variable', 'intent_confidence')
            use_llm = config.get('use_llm', True)
            model_name = config.get('model_name', 'gpt-3.5-turbo')
            
            if not input_text:
                output[output_intent_var] = 'unknown'
                output[output_confidence_var] = 0.0
                output['intent_recognition_success'] = True
                return output
            
            if use_llm:
                intent_descriptions = '\n'.join([
                    f"- {i['intent_id']}: {i['intent_name']} (示例: {'; '.join(i.get('examples', [])[:3])})"
                    for i in intents
                ])
                
                prompt = f"""请识别以下用户输入的意图。

可用意图：
{intent_descriptions}

用户输入：{input_text}

请以JSON格式返回结果，包含：
- intent: 识别出的意图ID
- confidence: 置信度（0-1）
- reasoning: 识别理由"""

                result = self.ai_service.generate_content(prompt, model_name)
                
                try:
                    result_data = json.loads(result)
                    output[output_intent_var] = result_data.get('intent', 'unknown')
                    output[output_confidence_var] = result_data.get('confidence', 0.0)
                    output['reasoning'] = result_data.get('reasoning', '')
                except:
                    output[output_intent_var] = 'unknown'
                    output[output_confidence_var] = 0.0
            else:
                input_lower = input_text.lower()
                best_intent = None
                best_score = 0.0
                
                for intent in intents:
                    keywords = intent.get('keywords', [])
                    examples = intent.get('examples', [])
                    
                    score = 0
                    for keyword in keywords:
                        if keyword.lower() in input_lower:
                            score += 0.3
                    
                    for example in examples:
                        if example.lower() in input_lower:
                            score += 0.2
                    
                    if score > best_score:
                        best_score = score
                        best_intent = intent
                
                output[output_intent_var] = best_intent['intent_id'] if best_intent else 'unknown'
                output[output_confidence_var] = min(best_score, 1.0)
            
            output['intent_recognition_success'] = True
            output['input_text'] = input_text
            output['all_intents'] = [
                {'intent_id': i['intent_id'], 'intent_name': i['intent_name']}
                for i in intents
            ]
            
        except Exception as e:
            logger.error(f"意图识别失败: {e}")
            output['intent_recognition_success'] = False
            output['error_message'] = str(e)
        
        return output
    
    def execute(self, config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(self.execute_async(config, context))
        finally:
            loop.close()


class CodeExecutionProcessor(BaseNodeProcessor):
    """代码执行节点处理器（整合扣子的代码能力）"""
    
    def __init__(self, node_type_code: str):
        super().__init__(node_type_code)
    
    def _get_config_schema(self) -> Dict[str, Any]:
        return {
            'code': {
                'type': 'string',
                'required': True,
                'label': '代码',
                'description': '要执行的Python代码',
                'multiline': True,
                'rows': 10,
                'placeholder': '输入您的Python代码，可使用 {{变量名}} 引用上下文变量'
            },
            'input_variables': {
                'type': 'array',
                'required': False,
                'label': '输入变量',
                'description': '需要传入的变量名列表',
                'items': {'type': 'string'}
            },
            'output_variables': {
                'type': 'array',
                'required': False,
                'label': '输出变量',
                'description': '代码中定义的需要输出的变量名列表',
                'items': {'type': 'string'}
            },
            'timeout': {
                'type': 'number',
                'required': False,
                'label': '超时时间（秒）',
                'default': 30,
                'min': 1,
                'max': 300
            },
            'sandbox_enabled': {
                'type': 'boolean',
                'required': False,
                'label': '启用沙箱',
                'default': True,
                'description': '是否在沙箱环境中执行代码'
            }
        }
    
    async def execute_async(self, config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """异步执行代码"""
        output = {}
        
        try:
            code = config.get('code', '')
            input_variables = config.get('input_variables', [])
            output_variables = config.get('output_variables', [])
            timeout = config.get('timeout', 30)
            sandbox_enabled = config.get('sandbox_enabled', True)
            
            local_vars = {}
            for var_name in input_variables:
                if var_name in context:
                    local_vars[var_name] = context[var_name]
            
            if sandbox_enabled:
                import restrictedpython
                result = restrictedpython.compile_restricted(code, '<string>', 'exec')
                if result.errors:
                    raise RuntimeError(f"代码编译错误: {result.errors}")
                
                glb = {
                    '__builtins__': restrictedpython.safe_builtins,
                    '_print_': print,
                    '_getattr_': getattr,
                    '_setattr_': setattr,
                    '_delattr_': delattr
                }
                exec(result.code, glb, local_vars)
            else:
                glb = {'__builtins__': __builtins__}
                exec(code, glb, local_vars)
            
            for var_name in output_variables:
                if var_name in local_vars:
                    output[var_name] = local_vars[var_name]
            
            output['code_execution_success'] = True
            
        except Exception as e:
            logger.error(f"代码执行失败: {e}")
            output['code_execution_success'] = False
            output['error_message'] = str(e)
        
        return output
    
    def execute(self, config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(self.execute_async(config, context))
        finally:
            loop.close()


class LoopProcessor(BaseNodeProcessor):
    """循环处理节点处理器（增强版）"""
    
    def __init__(self, node_type_code: str):
        super().__init__(node_type_code)
    
    def _get_config_schema(self) -> Dict[str, Any]:
        return {
            'loop_type': {
                'type': 'string',
                'required': True,
                'label': '循环类型',
                'default': 'for',
                'options': [
                    {'value': 'for', 'label': '计数循环'},
                    {'value': 'while', 'label': '条件循环'},
                    {'value': 'foreach', 'label': '遍历循环'}
                ]
            },
            'loop_variable': {
                'type': 'string',
                'required': True,
                'label': '循环变量名',
                'default': 'item',
                'description': '每次循环迭代的变量名'
            },
            'loop_source': {
                'type': 'string',
                'required': False,
                'label': '数据源',
                'description': '数据源变量名（用于foreach循环）'
            },
            'start_value': {
                'type': 'number',
                'required': False,
                'label': '起始值',
                'default': 0
            },
            'end_value': {
                'type': 'number',
                'required': False,
                'label': '结束值',
                'default': 10
            },
            'step': {
                'type': 'number',
                'required': False,
                'label': '步长',
                'default': 1
            },
            'condition': {
                'type': 'string',
                'required': False,
                'label': '循环条件',
                'description': 'while循环的条件表达式'
            },
            'max_iterations': {
                'type': 'number',
                'required': False,
                'label': '最大迭代次数',
                'default': 100,
                'min': 1,
                'max': 10000
            },
            'output_mode': {
                'type': 'string',
                'required': False,
                'label': '输出模式',
                'default': 'last',
                'options': [
                    {'value': 'last', 'label': '最后一次迭代结果'},
                    {'value': 'all', 'label': '所有迭代结果'},
                    {'value': 'collect', 'label': '收集指定变量'}
                ]
            },
            'collect_variable': {
                'type': 'string',
                'required': False,
                'label': '收集变量',
                'description': 'output_mode为collect时要收集的变量名'
            }
        }
    
    def execute(self, config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """执行循环处理"""
        output = {}
        
        try:
            loop_type = config.get('loop_type', 'for')
            loop_variable = config.get('loop_variable', 'item')
            loop_source = config.get('loop_source', '')
            start_value = config.get('start_value', 0)
            end_value = config.get('end_value', 10)
            step = config.get('step', 1)
            condition = config.get('condition', '')
            max_iterations = config.get('max_iterations', 100)
            output_mode = config.get('output_mode', 'last')
            collect_variable = config.get('collect_variable', '')
            
            loop_results = []
            iteration = 0
            
            if loop_type == 'for':
                for i in range(start_value, end_value, step):
                    if iteration >= max_iterations:
                        break
                    context[loop_variable] = i
                    context[f'{loop_variable}_index'] = iteration
                    loop_results.append(context.copy())
                    iteration += 1
                    
            elif loop_type == 'while':
                while iteration < max_iterations:
                    try:
                        should_continue = eval(condition, {}, context) if condition else True
                        if not should_continue:
                            break
                        
                        context[loop_variable] = iteration
                        context[f'{loop_variable}_index'] = iteration
                        loop_results.append(context.copy())
                        iteration += 1
                        
                    except Exception as e:
                        logger.warning(f"循环条件评估失败: {e}")
                        break
                        
            elif loop_type == 'foreach':
                source_data = context.get(loop_source, [])
                if isinstance(source_data, (list, str)):
                    for index, item in enumerate(source_data):
                        if iteration >= max_iterations:
                            break
                        context[loop_variable] = item
                        context[f'{loop_variable}_index'] = index
                        loop_results.append(context.copy())
                        iteration += 1
            
            if output_mode == 'last':
                output = loop_results[-1] if loop_results else {}
            elif output_mode == 'all':
                output['loop_results'] = loop_results
                output['iteration_count'] = len(loop_results)
            elif output_mode == 'collect':
                collected = []
                for result in loop_results:
                    if collect_variable in result:
                        collected.append(result[collect_variable])
                output[collect_variable] = collected
                output['collected_count'] = len(collected)
            
            output['loop_success'] = True
            output['iterations'] = len(loop_results)
            
        except Exception as e:
            logger.error(f"循环处理失败: {e}")
            output['loop_success'] = False
            output['error_message'] = str(e)
        
        return output


class ParallelProcessor(BaseNodeProcessor):
    """并行处理节点处理器"""
    
    def __init__(self, node_type_code: str):
        super().__init__(node_type_code)
    
    def _get_config_schema(self) -> Dict[str, Any]:
        return {
            'tasks': {
                'type': 'array',
                'required': True,
                'label': '并行任务',
                'description': '定义要并行执行的任务列表',
                'items': {
                    'type': 'object',
                    'properties': {
                        'task_id': {'type': 'string', 'label': '任务ID'},
                        'task_name': {'type': 'string', 'label': '任务名称'},
                        'task_type': {
                            'type': 'string', 
                            'label': '任务类型',
                            'options': [
                                {'value': 'api_call', 'label': 'API调用'},
                                {'value': 'data_process', 'label': '数据处理'},
                                {'value': 'llm_call', 'label': 'LLM调用'}
                            ]
                        },
                        'task_config': {'type': 'object', 'label': '任务配置'}
                    }
                }
            },
            'max_workers': {
                'type': 'number',
                'required': False,
                'label': '最大并发数',
                'default': 5,
                'min': 1,
                'max': 20
            },
            'timeout': {
                'type': 'number',
                'required': False,
                'label': '超时时间（秒）',
                'default': 60,
                'min': 1,
                'max': 300
            },
            'error_handling': {
                'type': 'string',
                'required': False,
                'label': '错误处理',
                'default': 'continue',
                'options': [
                    {'value': 'continue', 'label': '继续执行其他任务'},
                    {'value': 'fail_all', 'label': '一个失败全部失败'},
                    {'value': 'fail_any', 'label': '一个失败即停止'}
                ]
            },
            'output_mode': {
                'type': 'string',
                'required': False,
                'label': '输出模式',
                'default': 'all',
                'options': [
                    {'value': 'all', 'label': '所有任务结果'},
                    {'value': 'success', 'label': '仅成功结果'},
                    {'value': 'merged', 'label': '合并结果'}
                ]
            }
        }
    
    async def execute_async(self, config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """异步执行并行处理"""
        output = {}
        
        try:
            tasks = config.get('tasks', [])
            max_workers = config.get('max_workers', 5)
            timeout = config.get('timeout', 60)
            error_handling = config.get('error_handling', 'continue')
            output_mode = config.get('output_mode', 'all')
            
            async def execute_task(task: Dict[str, Any]) -> Dict[str, Any]:
                task_id = task.get('task_id', '')
                task_type = task.get('task_type', 'api_call')
                task_config = task.get('task_config', {})
                
                try:
                    if task_type == 'api_call':
                        result = await self._execute_api_call(task_config, context)
                    elif task_type == 'llm_call':
                        result = await self._execute_llm_call(task_config, context)
                    else:
                        result = {'task_id': task_id, 'status': 'completed'}
                    
                    result['task_id'] = task_id
                    result['task_name'] = task.get('task_name', '')
                    return result
                    
                except Exception as e:
                    return {
                        'task_id': task_id,
                        'task_name': task.get('task_name', ''),
                        'status': 'failed',
                        'error': str(e)
                    }
            
            semaphore = asyncio.Semaphore(max_workers)
            
            async def bounded_task(task):
                async with semaphore:
                    return await execute_task(task)
            
            task_coroutines = [bounded_task(task) for task in tasks]
            results = await asyncio.gather(*task_coroutines, return_exceptions=True)
            
            successful = [r for r in results if isinstance(r, dict) and r.get('status') == 'completed']
            failed = [r for r in results if isinstance(r, dict) and r.get('status') == 'failed']
            
            if error_handling == 'fail_all' and failed:
                raise RuntimeError(f"任务执行失败: {failed[0].get('error', '未知错误')}")
            
            if output_mode == 'all':
                output['task_results'] = results
            elif output_mode == 'success':
                output['task_results'] = successful
            elif output_mode == 'merged':
                merged = {}
                for r in successful:
                    merged.update(r)
                output['merged_result'] = merged
            
            output['parallel_success'] = len(failed) == 0
            output['total_tasks'] = len(tasks)
            output['completed_tasks'] = len(successful)
            output['failed_tasks'] = len(failed)
            
        except Exception as e:
            logger.error(f"并行处理失败: {e}")
            output['parallel_success'] = False
            output['error_message'] = str(e)
        
        return output
    
    async def _execute_api_call(self, config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """执行API调用"""
        import aiohttp
        
        output = {}
        try:
            url = config.get('url', '')
            method = config.get('method', 'GET')
            headers = config.get('headers', {})
            body = config.get('body', '')
            
            for key, value in context.items():
                url = url.replace(f'{{{{{key}}}}}', str(value))
                if isinstance(body, str):
                    body = body.replace(f'{{{{{key}}}}}', str(value))
            
            timeout = aiohttp.ClientTimeout(total=config.get('timeout', 30))
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.request(method, url, headers=headers, data=body) as response:
                    output['status_code'] = response.status
                    output['response_time'] = response.elapsed.total_seconds()
                    if 'application/json' in response.headers.get('content-type', ''):
                        output['response_body'] = await response.json()
                    else:
                        output['response_body'] = await response.text()
                    output['success'] = response.status < 400
                    
        except Exception as e:
            output['success'] = False
            output['error'] = str(e)
        
        return output
    
    async def _execute_llm_call(self, config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """执行LLM调用"""
        from apps.ai.services.ai_analysis_service import AIAnalysisService
        
        ai_service = AIAnalysisService()
        prompt = config.get('prompt', '')
        model_name = config.get('model_name', 'gpt-3.5-turbo')
        
        for key, value in context.items():
            prompt = prompt.replace(f'{{{{{key}}}}}', str(value))
        
        result = ai_service.generate_content(prompt, model_name)
        
        return {
            'success': True,
            'result': result
        }
    
    def execute(self, config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(self.execute_async(config, context))
        finally:
            loop.close()


class VariableAggregationProcessor(BaseNodeProcessor):
    """变量聚合节点处理器（整合扣子的变量聚合能力）"""
    
    def __init__(self, node_type_code: str):
        super().__init__(node_type_code)
    
    def _get_config_schema(self) -> Dict[str, Any]:
        return {
            'source_variables': {
                'type': 'array',
                'required': True,
                'label': '源变量',
                'description': '要聚合的变量列表',
                'items': {'type': 'string'}
            },
            'aggregation_type': {
                'type': 'string',
                'required': True,
                'label': '聚合类型',
                'default': 'object',
                'options': [
                    {'value': 'object', 'label': '对象聚合'},
                    {'value': 'array', 'label': '数组聚合'},
                    {'value': 'string', 'label': '字符串拼接'},
                    {'value': 'custom', 'label': '自定义格式'}
                ]
            },
            'output_variable': {
                'type': 'string',
                'required': True,
                'label': '输出变量名'
            },
            'custom_format': {
                'type': 'string',
                'required': False,
                'label': '自定义格式',
                'description': '使用 {{变量名}} 占位符',
                'multiline': True
            },
            'delimiter': {
                'type': 'string',
                'required': False,
                'label': '分隔符',
                'default': ', '
            }
        }
    
    def execute(self, config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """执行变量聚合"""
        output = {}
        
        try:
            source_variables = config.get('source_variables', [])
            aggregation_type = config.get('aggregation_type', 'object')
            output_variable = config.get('output_variable')
            custom_format = config.get('custom_format', '')
            delimiter = config.get('delimiter', ', ')
            
            if aggregation_type == 'object':
                aggregated = {}
                for var_name in source_variables:
                    if var_name in context:
                        aggregated[var_name] = context[var_name]
                output[output_variable] = aggregated
                
            elif aggregation_type == 'array':
                aggregated = []
                for var_name in source_variables:
                    if var_name in context:
                        value = context[var_name]
                        if isinstance(value, list):
                            aggregated.extend(value)
                        else:
                            aggregated.append(value)
                output[output_variable] = aggregated
                
            elif aggregation_type == 'string':
                parts = []
                for var_name in source_variables:
                    if var_name in context:
                        value = context[var_name]
                        if isinstance(value, (list, dict)):
                            parts.append(str(json.dumps(value, ensure_ascii=False)))
                        else:
                            parts.append(str(value))
                output[output_variable] = delimiter.join(parts)
                
            elif aggregation_type == 'custom':
                result = custom_format
                for var_name in source_variables:
                    if var_name in context:
                        value = context[var_name]
                        if isinstance(value, (list, dict)):
                            value = json.dumps(value, ensure_ascii=False)
                        result = result.replace(f'{{{{{var_name}}}}}', str(value))
                output[output_variable] = result
            
            output['aggregation_success'] = True
            output['source_variables'] = source_variables
            output['aggregation_type'] = aggregation_type
            
        except Exception as e:
            logger.error(f"变量聚合失败: {e}")
            output['aggregation_success'] = False
            output['error_message'] = str(e)
        
        return output


class QuestionAnswerProcessor(BaseNodeProcessor):
    """问答交互节点处理器（整合扣子的对话交互能力）"""
    
    def __init__(self, node_type_code: str):
        super().__init__(node_type_code)
        self.ai_service = AIAnalysisService()
    
    def _get_config_schema(self) -> Dict[str, Any]:
        return {
            'question': {
                'type': 'string',
                'required': True,
                'label': '问题',
                'description': '要向用户提出的问题',
                'multiline': True
            },
            'question_variable': {
                'type': 'string',
                'required': False,
                'label': '问题变量',
                'description': '动态问题来源变量名'
            },
            'answer_variable': {
                'type': 'string',
                'required': True,
                'label': '答案变量',
                'default': 'user_answer'
            },
            'input_type': {
                'type': 'string',
                'required': False,
                'label': '输入类型',
                'default': 'text',
                'options': [
                    {'value': 'text', 'label': '文本输入'},
                    {'value': 'choice', 'label': '选择输入'},
                    {'value': 'file', 'label': '文件上传'}
                ]
            },
            'choices': {
                'type': 'array',
                'required': False,
                'label': '选项列表',
                'description': '选择输入时的选项',
                'items': {'type': 'string'}
            },
            'default_answer': {
                'type': 'string',
                'required': False,
                'label': '默认值',
                'description': '用户未输入时的默认值'
            },
            'validation': {
                'type': 'object',
                'required': False,
                'label': '验证规则',
                'properties': {
                    'required': {'type': 'boolean', 'label': '是否必填'},
                    'min_length': {'type': 'number', 'label': '最小长度'},
                    'max_length': {'type': 'number', 'label': '最大长度'},
                    'pattern': {'type': 'string', 'label': '正则表达式'}
                }
            }
        }
    
    def execute(self, config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """执行问答交互"""
        output = {}
        
        try:
            question_variable = config.get('question_variable')
            if question_variable and question_variable in context:
                question = context[question_variable]
            else:
                question = config.get('question', '')
            
            answer_variable = config.get('answer_variable', 'user_answer')
            input_type = config.get('input_type', 'text')
            choices = config.get('choices', [])
            default_answer = config.get('default_answer', '')
            validation = config.get('validation', {})
            
            output['question'] = question
            output['answer_variable'] = answer_variable
            output['input_type'] = input_type
            output['choices'] = choices
            output['requires_user_input'] = True
            
            if answer_variable in context:
                user_answer = context[answer_variable]
                
                is_valid = True
                if validation.get('required') and not user_answer:
                    is_valid = False
                    output['validation_error'] = '此项为必填项'
                
                if is_valid and validation.get('min_length') and len(str(user_answer)) < validation['min_length']:
                    is_valid = False
                    output['validation_error'] = f'输入长度不能少于{validation["min_length"]}个字符'
                
                if is_valid and validation.get('max_length') and len(str(user_answer)) > validation['max_length']:
                    is_valid = False
                    output['validation_error'] = f'输入长度不能超过{validation["max_length"]}个字符'
                
                if is_valid and validation.get('pattern'):
                    import re
                    if not re.match(validation['pattern'], str(user_answer)):
                        is_valid = False
                        output['validation_error'] = '输入格式不正确'
                
                if is_valid:
                    output[answer_variable] = user_answer
                    output['question_answer_success'] = True
                else:
                    output['question_answer_success'] = False
            else:
                output[answer_variable] = default_answer
                output['question_answer_success'] = True
                output['used_default'] = True
            
        except Exception as e:
            logger.error(f"问答交互失败: {e}")
            output['question_answer_success'] = False
            output['error_message'] = str(e)
        
        return output


@NodeProcessorRegistry.register('knowledge_retrieval')
class KnowledgeRetrievalProcessorDify(KnowledgeRetrievalProcessor):
    """Dify风格知识检索节点"""
    pass


@NodeProcessorRegistry.register('intent_recognition')
class IntentRecognitionProcessorCoze(IntentRecognitionProcessor):
    """扣子风格意图识别节点"""
    pass


@NodeProcessorRegistry.register('code_execution')
class CodeExecutionProcessorCoze(CodeExecutionProcessor):
    """扣子风格代码执行节点"""
    pass


@NodeProcessorRegistry.register('loop')
class LoopProcessorEnhanced(LoopProcessor):
    """增强版循环节点"""
    pass


@NodeProcessorRegistry.register('parallel')
class ParallelProcessorEnhanced(ParallelProcessor):
    """增强版并行处理节点"""
    pass


@NodeProcessorRegistry.register('variable_aggregation')
class VariableAggregationProcessorCoze(VariableAggregationProcessor):
    """扣子风格变量聚合节点"""
    pass


@NodeProcessorRegistry.register('question_answer')
class QuestionAnswerProcessorCoze(QuestionAnswerProcessor):
    """扣子风格问答交互节点"""
    pass
