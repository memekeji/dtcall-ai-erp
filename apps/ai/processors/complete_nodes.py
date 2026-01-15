"""
Complete Node Processors for DTCall Workflow Designer
Comprehensive node types comparable to Dify and Coze platforms
"""

import json
import re
import ast
import logging
from typing import Dict, Any, List, Optional
from abc import ABC, abstractmethod
import asyncio
from datetime import datetime, timedelta
from urllib.parse import urlencode, quote
import hashlib

from apps.ai.processors.base_processor import BaseNodeProcessor, NodeProcessorRegistry
from apps.ai.services.ai_analysis_service import AIAnalysisService
from apps.ai.services.rag_service import RAGService
from apps.ai.services.intent_recognition_service import IntentRecognitionService

logger = logging.getLogger(__name__)


class TextProcessingProcessor(BaseNodeProcessor):
    """Text processing node for text manipulation and transformation"""
    
    def __init__(self, node_type_code: str):
        super().__init__(node_type_code)
        self.operations = {
            'substring': self._substring,
            'replace': self._replace,
            'trim': self._trim,
            'split': self._split,
            'join': self._join,
            'case_convert': self._case_convert,
            'regex_match': self._regex_match,
            'regex_extract': self._regex_extract,
            'length': self._length,
            'format_date': self._format_date,
            'json_parse': self._json_parse,
            'json_format': self._json_format,
            'base64_encode': self._base64_encode,
            'base64_decode': self._base64_decode
        }
    
    def _get_config_schema(self) -> Dict[str, Any]:
        return {
            'text_variable': {
                'type': 'string',
                'required': True,
                'label': 'Input Text Variable',
                'placeholder': 'Enter variable name'
            },
            'operation': {
                'type': 'select',
                'required': True,
                'label': 'Operation Type',
                'options': [
                    {'value': 'substring', 'label': 'Substring'},
                    {'value': 'replace', 'label': 'Replace'},
                    {'value': 'trim', 'label': 'Trim'},
                    {'value': 'split', 'label': 'Split'},
                    {'value': 'join', 'label': 'Join'},
                    {'value': 'case_convert', 'label': 'Case Conversion'},
                    {'value': 'regex_match', 'label': 'Regex Match'},
                    {'value': 'regex_extract', 'label': 'Regex Extract'},
                    {'value': 'length', 'label': 'Get Length'},
                    {'value': 'format_date', 'label': 'Date Format'},
                    {'value': 'json_parse', 'label': 'JSON Parse'},
                    {'value': 'json_format', 'label': 'JSON Format'},
                    {'value': 'base64_encode', 'label': 'Base64 Encode'},
                    {'value': 'base64_decode', 'label': 'Base64 Decode'}
                ]
            },
            'operation_params': {
                'type': 'object',
                'required': False,
                'label': 'Operation Parameters',
                'fields': {
                    'start': {'type': 'number', 'label': 'Start Position'},
                    'end': {'type': 'number', 'label': 'End Position'},
                    'old_str': {'type': 'string', 'label': 'Old String'},
                    'new_str': {'type': 'string', 'label': 'New String'},
                    'separator': {'type': 'string', 'label': 'Separator'},
                    'max_split': {'type': 'number', 'label': 'Max Split'},
                    'join_str': {'type': 'string', 'label': 'Join String'},
                    'case_type': {'type': 'select', 'options': [
                        {'value': 'upper', 'label': 'Uppercase'},
                        {'value': 'lower', 'label': 'Lowercase'},
                        {'value': 'title', 'label': 'Title Case'}
                    ]},
                    'pattern': {'type': 'string', 'label': 'Regex Pattern'},
                    'date_format': {'type': 'string', 'label': 'Date Format', 'default': '%Y-%m-%d %H:%M:%S'}
                }
            },
            'output_variable': {
                'type': 'string',
                'required': True,
                'label': 'Output Variable',
                'default': 'text_result'
            }
        }
    
    async def execute_async(self, config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        text_variable = config.get('text_variable', '')
        text = self._get_variable_value(text_variable, context)
        operation = config.get('operation', 'substring')
        params = config.get('operation_params', {})
        output_var = config.get('output_variable', 'text_result')
        
        if text is None:
            return {output_var: '', 'status': 'completed'}
        
        if operation in self.operations:
            result = await self.operations[operation](text, params, context)
        else:
            result = text
        
        return {output_var: result, 'status': 'completed'}
    
    async def _substring(self, text: str, params: Dict, context: Dict) -> str:
        start = params.get('start', 0)
        end = params.get('end')
        return text[start:end] if end else text[start:]
    
    async def _replace(self, text: str, params: Dict, context: Dict) -> str:
        old_str = params.get('old_str', '')
        new_str = params.get('new_str', '')
        return text.replace(old_str, new_str)
    
    async def _trim(self, text: str, params: Dict, context: Dict) -> str:
        return text.strip()
    
    async def _split(self, text: str, params: Dict, context: Dict) -> List[str]:
        separator = params.get('separator', ',')
        max_split = params.get('max_split', 0)
        if max_split > 0:
            return text.split(separator, max_split)
        return text.split(separator)
    
    async def _join(self, text: str, params: Dict, context: Dict) -> str:
        if isinstance(text, list):
            join_str = params.get('join_str', '')
            return join_str.join(text)
        return str(text)
    
    async def _case_convert(self, text: str, params: Dict, context: Dict) -> str:
        case_type = params.get('case_type', 'lower')
        if case_type == 'upper':
            return text.upper()
        elif case_type == 'title':
            return text.title()
        return text.lower()
    
    async def _regex_match(self, text: str, params: Dict, context: Dict) -> bool:
        pattern = params.get('pattern', '')
        return bool(re.match(pattern, text))
    
    async def _regex_extract(self, text: str, params: Dict, context: Dict) -> str:
        pattern = params.get('pattern', '')
        match = re.search(pattern, text)
        return match.group(0) if match else ''
    
    async def _length(self, text: str, params: Dict, context: Dict) -> int:
        return len(text)
    
    async def _format_date(self, text: str, params: Dict, context: Dict) -> str:
        try:
            date_format = params.get('date_format', '%Y-%m-%d %H:%M:%S')
            parsed_date = datetime.fromisoformat(text)
            return parsed_date.strftime(date_format)
        except:
            return text
    
    async def _json_parse(self, text: str, params: Dict, context: Dict) -> Dict:
        try:
            return json.loads(text)
        except:
            return {}
    
    async def _json_format(self, text: str, params: Dict, context: Dict) -> str:
        try:
            if isinstance(text, dict):
                return json.dumps(text, ensure_ascii=False, indent=2)
            return text
        except:
            return text
    
    async def _base64_encode(self, text: str, params: Dict, context: Dict) -> str:
        import base64
        return base64.b64encode(text.encode()).decode()
    
    async def _base64_decode(self, text: str, params: Dict, context: Dict) -> str:
        import base64
        try:
            return base64.b64decode(text.encode()).decode()
        except:
            return text


@NodeProcessorRegistry.register('document_extractor')
class DocumentExtractorProcessor(BaseNodeProcessor):
    """Document extraction node for extracting content from various document formats"""
    
    def __init__(self, node_type_code: str):
        super().__init__(node_type_code)
        self.ai_service = AIAnalysisService()
    
    def _get_config_schema(self) -> Dict[str, Any]:
        return {
            'file_variable': {
                'type': 'string',
                'required': True,
                'label': 'File Variable',
                'placeholder': 'Enter file path variable'
            },
            'file_type': {
                'type': 'select',
                'required': True,
                'label': 'File Type',
                'options': [
                    {'value': 'pdf', 'label': 'PDF Document'},
                    {'value': 'word', 'label': 'Word Document'},
                    {'value': 'excel', 'label': 'Excel Spreadsheet'},
                    {'value': 'txt', 'label': 'Plain Text'},
                    {'value': 'markdown', 'label': 'Markdown'},
                    {'value': 'html', 'label': 'HTML'},
                    {'value': 'csv', 'label': 'CSV'},
                    {'value': 'image', 'label': 'Image'}
                ]
            },
            'extraction_method': {
                'type': 'select',
                'required': False,
                'label': 'Extraction Method',
                'options': [
                    {'value': 'text', 'label': 'Text Extraction'},
                    {'value': 'table', 'label': 'Table Extraction'},
                    {'value': 'ocr', 'label': 'OCR Recognition'},
                    {'value': 'structured', 'label': 'Structured Extraction'}
                ],
                'default': 'text'
            },
            'output_variable': {
                'type': 'string',
                'required': True,
                'label': 'Output Variable',
                'default': 'extracted_content'
            }
        }
    
    async def execute_async(self, config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        file_var = config.get('file_variable', '')
        file_path = self._get_variable_value(file_var, context)
        file_type = config.get('file_type', 'txt')
        method = config.get('extraction_method', 'text')
        output_var = config.get('output_variable', 'extracted_content')
        
        if not file_path:
            return {output_var: '', 'status': 'completed'}
        
        try:
            if file_type == 'image' and method == 'ocr':
                content = await self._extract_from_image(file_path)
            elif file_type in ['pdf', 'word', 'txt', 'markdown', 'html']:
                content = await self._extract_from_document(file_path, file_type)
            elif file_type in ['excel', 'csv']:
                content = await self._extract_from_spreadsheet(file_path, file_type, method)
            else:
                content = ''
            
            return {output_var: content, 'status': 'completed'}
        except Exception as e:
            logger.error(f"Document extraction failed: {e}")
            return {output_var: '', 'error': str(e), 'status': 'failed'}
    
    async def _extract_from_image(self, file_path: str) -> str:
        return await self.ai_service.extract_text_from_image(file_path)
    
    async def _extract_from_document(self, file_path: str, file_type: str) -> str:
        if file_type == 'pdf':
            return await self._extract_from_pdf(file_path)
        elif file_type == 'word':
            return await self._extract_from_word(file_path)
        else:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    return f.read()
            except:
                return ''
    
    async def _extract_from_pdf(self, file_path: str) -> str:
        try:
            import PyPDF2
            with open(file_path, 'rb') as f:
                reader = PyPDF2.PdfReader(f)
                return ''.join(page.extract_text() for page in reader.pages)
        except Exception as e:
            logger.error(f"PDF extraction error: {e}")
            return ''
    
    async def _extract_from_word(self, file_path: str) -> str:
        try:
            from docx import Document
            doc = Document(file_path)
            return '\n'.join(para.text for para in doc.paragraphs)
        except Exception as e:
            logger.error(f"Word extraction error: {e}")
            return ''
    
    async def _extract_from_spreadsheet(self, file_path: str, file_type: str, method: str) -> Any:
        import pandas as pd
        try:
            if file_type == 'csv':
                df = pd.read_csv(file_path)
            else:
                df = pd.read_excel(file_path)
            
            if method == 'table':
                return df.to_dict('records')
            elif method == 'structured':
                return df.to_dict('list')
            else:
                return df.to_string()
        except Exception as e:
            logger.error(f"Spreadsheet extraction error: {e}")
            return ''


@NodeProcessorRegistry.register('http_request')
class HttpRequestProcessor(BaseNodeProcessor):
    """Enhanced HTTP request node with more options"""
    
    def __init__(self, node_type_code: str):
        super().__init__(node_type_code)
    
    def _get_config_schema(self) -> Dict[str, Any]:
        return {
            'url': {
                'type': 'string',
                'required': True,
                'label': 'Request URL',
                'placeholder': 'https://api.example.com/endpoint'
            },
            'method': {
                'type': 'select',
                'required': True,
                'label': 'Request Method',
                'options': [
                    {'value': 'GET', 'label': 'GET'},
                    {'value': 'POST', 'label': 'POST'},
                    {'value': 'PUT', 'label': 'PUT'},
                    {'value': 'PATCH', 'label': 'PATCH'},
                    {'value': 'DELETE', 'label': 'DELETE'},
                    {'value': 'HEAD', 'label': 'HEAD'}
                ]
            },
            'headers': {
                'type': 'object',
                'required': False,
                'label': 'Request Headers'
            },
            'params': {
                'type': 'object',
                'required': False,
                'label': 'Query Parameters'
            },
            'body': {
                'type': 'text',
                'required': False,
                'label': 'Request Body',
                'placeholder': 'JSON body'
            },
            'body_type': {
                'type': 'select',
                'required': False,
                'label': 'Body Type',
                'options': [
                    {'value': 'none', 'label': 'None'},
                    {'value': 'json', 'label': 'JSON'},
                    {'value': 'form', 'label': 'Form URL Encoded'},
                    {'value': 'form-data', 'label': 'Multipart Form Data'},
                    {'value': 'raw', 'label': 'Raw Text'}
                ]
            },
            'timeout': {
                'type': 'number',
                'required': False,
                'label': 'Timeout (seconds)',
                'default': 30
            },
            'retry_times': {
                'type': 'number',
                'required': False,
                'label': 'Retry Times',
                'default': 0
            },
            'output_variable': {
                'type': 'string',
                'required': True,
                'label': 'Output Variable',
                'default': 'http_response'
            }
        }
    
    async def execute_async(self, config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        import httpx
        
        url = self._render_template(config.get('url', ''), context)
        method = config.get('method', 'GET')
        headers = config.get('headers', {})
        params = config.get('params', {})
        body = config.get('body', '')
        body_type = config.get('body_type', 'none')
        timeout = config.get('timeout', 30)
        retry_times = config.get('retry_times', 0)
        output_var = config.get('output_variable', 'http_response')
        
        rendered_body = self._render_template(body, context) if body else None
        
        client_kwargs = {
            'timeout': timeout,
            'follow_redirects': True
        }
        
        async with httpx.AsyncClient(**client_kwargs) as client:
            for attempt in range(retry_times + 1):
                try:
                    request_kwargs = {
                        'url': url,
                        'headers': headers,
                        'params': params
                    }
                    
                    if method in ['POST', 'PUT', 'PATCH'] and body_type != 'none':
                        if body_type == 'json':
                            request_kwargs['json'] = json.loads(rendered_body) if rendered_body else {}
                        elif body_type == 'form':
                            request_kwargs['data'] = urlencode(json.loads(rendered_body)) if rendered_body else {}
                        elif body_type == 'raw':
                            request_kwargs['content'] = rendered_body.encode() if rendered_body else b''
                    
                    response = await client.request(method, **request_kwargs)
                    
                    result = {
                        'status_code': response.status_code,
                        'headers': dict(response.headers),
                        'body': response.text,
                        'json': None
                    }
                    
                    if response.headers.get('content-type', '').startswith('application/json'):
                        try:
                            result['json'] = response.json()
                        except:
                            pass
                    
                    return {
                        output_var: result,
                        'status_code': response.status_code,
                        'status': 'completed' if response.status_code < 400 else 'failed'
                    }
                    
                except Exception as e:
                    if attempt == retry_times:
                        return {output_var: {}, 'error': str(e), 'status': 'failed'}
        
        return {output_var: {}, 'status': 'failed'}


class DatabaseProcessor(BaseNodeProcessor):
    """Database operation node for SQL queries"""
    
    def __init__(self, node_type_code: str):
        super().__init__(node_type_code)
    
    def _get_config_schema(self) -> Dict[str, Any]:
        return {
            'connection_id': {
                'type': 'string',
                'required': True,
                'label': 'Database Connection',
                'placeholder': 'Select database connection'
            },
            'operation': {
                'type': 'select',
                'required': True,
                'label': 'Operation Type',
                'options': [
                    {'value': 'query', 'label': 'Query (SELECT)'},
                    {'value': 'execute', 'label': 'Execute (INSERT/UPDATE/DELETE)'},
                    {'value': 'call', 'label': 'Stored Procedure'}
                ]
            },
            'sql': {
                'type': 'text',
                'required': True,
                'label': 'SQL Statement',
                'placeholder': 'SELECT * FROM table WHERE ...'
            },
            'params': {
                'type': 'object',
                'required': False,
                'label': 'SQL Parameters'
            },
            'output_variable': {
                'type': 'string',
                'required': True,
                'label': 'Output Variable',
                'default': 'query_result'
            }
        }
    
    async def execute_async(self, config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        from django.db import connection
        
        connection_id = config.get('connection_id', '')
        operation = config.get('operation', 'query')
        sql = self._render_template(config.get('sql', ''), context)
        params = config.get('params', {})
        output_var = config.get('output_variable', 'query_result')
        
        try:
            rendered_params = {k: self._render_template(str(v), context) for k, v in params.items()}
            
            with connection.cursor() as cursor:
                if operation == 'query':
                    cursor.execute(sql, rendered_params)
                    columns = [col[0] for col in cursor.description]
                    rows = cursor.fetchall()
                    result = [dict(zip(columns, row)) for row in rows]
                else:
                    cursor.execute(sql, rendered_params)
                    result = {
                        'affected_rows': cursor.rowcount,
                        'last_insert_id': cursor.lastrowid
                    }
            
            return {output_var: result, 'status': 'completed'}
        except Exception as e:
            logger.error(f"Database operation failed: {e}")
            return {output_var: {}, 'error': str(e), 'status': 'failed'}


class TemplateProcessor(BaseNodeProcessor):
    """Template rendering node for text templating"""
    
    def __init__(self, node_type_code: str):
        super().__init__(node_type_code)
    
    def _get_config_schema(self) -> Dict[str, Any]:
        return {
            'template': {
                'type': 'text',
                'required': True,
                'label': 'Template Content',
                'placeholder': 'Hello {{name}}, your score is {{score}}'
            },
            'data_variable': {
                'type': 'string',
                'required': True,
                'label': 'Data Variable',
                'placeholder': 'Enter data object variable name'
            },
            'template_engine': {
                'type': 'select',
                'required': False,
                'label': 'Template Engine',
                'options': [
                    {'value': 'jinja2', 'label': 'Jinja2'},
                    {'value': 'simple', 'label': 'Simple Template'}
                ],
                'default': 'jinja2'
            },
            'output_variable': {
                'type': 'string',
                'required': True,
                'label': 'Output Variable',
                'default': 'rendered_text'
            }
        }
    
    async def execute_async(self, config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        from jinja2 import Template as Jinja2Template, Environment, BaseLoader
        
        template_text = config.get('template', '')
        data_var = config.get('data_variable', 'data')
        engine = config.get('template_engine', 'jinja2')
        output_var = config.get('output_variable', 'rendered_text')
        
        data = self._get_variable_value(data_var, context) or {}
        
        try:
            if engine == 'jinja2':
                env = Environment(loader=BaseLoader())
                template = env.from_string(template_text)
                result = template.render(**data) if isinstance(data, dict) else str(data)
            else:
                rendered = template_text
                if isinstance(data, dict):
                    for key, value in data.items():
                        rendered = rendered.replace('{{' + key + '}}', str(value))
                result = rendered
            
            return {output_var: result, 'status': 'completed'}
        except Exception as e:
            logger.error(f"Template rendering failed: {e}")
            return {output_var: '', 'error': str(e), 'status': 'failed'}


@NodeProcessorRegistry.register('sentiment_analysis')
class SentimentAnalysisProcessor(BaseNodeProcessor):
    """Sentiment analysis node for text sentiment classification"""
    
    def __init__(self, node_type_code: str):
        super().__init__(node_type_code)
        self.ai_service = AIAnalysisService()
    
    def _get_config_schema(self) -> Dict[str, Any]:
        return {
            'text_variable': {
                'type': 'string',
                'required': True,
                'label': 'Input Text Variable',
                'placeholder': 'Enter variable name'
            },
            'analysis_type': {
                'type': 'select',
                'required': False,
                'label': 'Analysis Type',
                'options': [
                    {'value': 'basic', 'label': 'Basic (Positive/Negative)'},
                    {'value': 'fine', 'label': 'Fine-grained Sentiment'},
                    {'value': 'emotion', 'label': 'Emotion Recognition'}
                ],
                'default': 'basic'
            },
            'output_variable': {
                'type': 'string',
                'required': True,
                'label': 'Output Variable',
                'default': 'sentiment_result'
            }
        }
    
    async def execute_async(self, config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        text_var = config.get('text_variable', '')
        text = self._get_variable_value(text_var, context)
        analysis_type = config.get('analysis_type', 'basic')
        output_var = config.get('output_variable', 'sentiment_result')
        
        if not text:
            return {output_var: {'sentiment': 'neutral', 'score': 0.5}, 'status': 'completed'}
        
        try:
            if analysis_type == 'emotion':
                result = await self.ai_service.analyze_emotion(text)
            else:
                sentiment, score = await self.ai_service.analyze_sentiment(text, analysis_type)
                result = {'sentiment': sentiment, 'score': score}
            
            return {output_var: result, 'status': 'completed'}
        except Exception as e:
            logger.error(f"Sentiment analysis failed: {e}")
            return {output_var: {'sentiment': 'unknown', 'score': 0}, 'error': str(e), 'status': 'failed'}


@NodeProcessorRegistry.register('image_processing')
class ImageProcessor(BaseNodeProcessor):
    """Image processing node for image manipulation"""
    
    def __init__(self, node_type_code: str):
        super().__init__(node_type_code)
    
    def _get_config_schema(self) -> Dict[str, Any]:
        return {
            'image_variable': {
                'type': 'string',
                'required': True,
                'label': 'Image Variable',
                'placeholder': 'Enter image path variable'
            },
            'operation': {
                'type': 'select',
                'required': True,
                'label': 'Operation Type',
                'options': [
                    {'value': 'resize', 'label': 'Resize'},
                    {'value': 'crop', 'label': 'Crop'},
                    {'value': 'rotate', 'label': 'Rotate'},
                    {'value': 'format', 'label': 'Format Conversion'},
                    {'value': 'compress', 'label': 'Compress'},
                    {'value': 'watermark', 'label': 'Add Watermark'},
                    {'value': 'ocr', 'label': 'OCR Recognition'},
                    {'value': 'describe', 'label': 'Image Description'}
                ]
            },
            'operation_params': {
                'type': 'object',
                'required': False,
                'label': 'Operation Parameters',
                'fields': {
                    'width': {'type': 'number', 'label': 'Width'},
                    'height': {'type': 'number', 'label': 'Height'},
                    'crop_x': {'type': 'number', 'label': 'Crop X'},
                    'crop_y': {'type': 'number', 'label': 'Crop Y'},
                    'crop_w': {'type': 'number', 'label': 'Crop Width'},
                    'crop_h': {'type': 'number', 'label': 'Crop Height'},
                    'rotate_angle': {'type': 'number', 'label': 'Rotation Angle'},
                    'output_format': {'type': 'select', 'options': [
                        {'value': 'jpeg', 'label': 'JPEG'},
                        {'value': 'png', 'label': 'PNG'},
                        {'value': 'webp', 'label': 'WebP'}
                    ]},
                    'quality': {'type': 'number', 'label': 'Quality (1-100)'},
                    'watermark_text': {'type': 'string', 'label': 'Watermark Text'}
                }
            },
            'output_variable': {
                'type': 'string',
                'required': True,
                'label': 'Output Variable',
                'default': 'image_result'
            }
        }
    
    async def execute_async(self, config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        from PIL import Image, ImageDraw
        import os
        
        image_var = config.get('image_variable', '')
        image_path = self._get_variable_value(image_var, context)
        operation = config.get('operation', 'resize')
        params = config.get('operation_params', {})
        output_var = config.get('output_variable', 'image_result')
        
        if not image_path or not os.path.exists(image_path):
            return {output_var: '', 'error': 'Image not found', 'status': 'failed'}
        
        try:
            with Image.open(image_path) as img:
                if operation == 'resize':
                    width = params.get('width', img.width)
                    height = params.get('height', img.height)
                    img = img.resize((width, height), Image.LANCZOS)
                elif operation == 'crop':
                    x = params.get('crop_x', 0)
                    y = params.get('crop_y', 0)
                    w = params.get('crop_w', img.width // 2)
                    h = params.get('crop_h', img.height // 2)
                    img = img.crop((x, y, x + w, y + h))
                elif operation == 'rotate':
                    angle = params.get('rotate_angle', 0)
                    img = img.rotate(angle, expand=True)
                elif operation == 'watermark':
                    text = params.get('watermark_text', 'Watermark')
                    draw = ImageDraw.Draw(img)
                    draw.text((10, 10), text, fill=(255, 255, 255))
                elif operation == 'ocr':
                    return {output_var: await self._ocr_image(image_path), 'status': 'completed'}
                elif operation == 'describe':
                    return {output_var: await self._describe_image(image_path), 'status': 'completed'}
                
                output_path = image_path
                img.save(output_path)
                return {output_var: output_path, 'status': 'completed'}
        except Exception as e:
            logger.error(f"Image processing failed: {e}")
            return {output_var: '', 'error': str(e), 'status': 'failed'}
    
    async def _ocr_image(self, image_path: str) -> str:
        from apps.ai.services.ai_analysis_service import AIAnalysisService
        service = AIAnalysisService()
        return await service.extract_text_from_image(image_path)
    
    async def _describe_image(self, image_path: str) -> str:
        return "Image description requires vision model API"


@NodeProcessorRegistry.register('audio_processing')
class AudioProcessor(BaseNodeProcessor):
    """Audio processing node for speech and audio operations"""
    
    def __init__(self, node_type_code: str):
        super().__init__(node_type_code)
        self.stt_service = None
    
    def _get_config_schema(self) -> Dict[str, Any]:
        return {
            'audio_variable': {
                'type': 'string',
                'required': True,
                'label': 'Audio Variable',
                'placeholder': 'Enter audio path variable'
            },
            'operation': {
                'type': 'select',
                'required': True,
                'label': 'Operation Type',
                'options': [
                    {'value': 'stt', 'label': 'Speech to Text (STT)'},
                    {'value': 'tts', 'label': 'Text to Speech (TTS)'},
                    {'value': 'duration', 'label': 'Get Duration'},
                    {'value': 'format', 'label': 'Format Conversion'},
                    {'value': 'compress', 'label': 'Compress'}
                ]
            },
            'operation_params': {
                'type': 'object',
                'required': False,
                'label': 'Operation Parameters',
                'fields': {
                    'text': {'type': 'text', 'label': 'Text to Convert'},
                    'language': {'type': 'string', 'label': 'Language', 'default': 'zh-CN'},
                    'output_format': {'type': 'select', 'options': [
                        {'value': 'mp3', 'label': 'MP3'},
                        {'value': 'wav', 'label': 'WAV'},
                        {'value': 'ogg', 'label': 'OGG'}
                    ]},
                    'voice': {'type': 'string', 'label': 'Voice Type'},
                    'speed': {'type': 'number', 'label': 'Speed', 'default': 1.0}
                }
            },
            'output_variable': {
                'type': 'string',
                'required': True,
                'label': 'Output Variable',
                'default': 'audio_result'
            }
        }
    
    async def execute_async(self, config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        audio_var = config.get('audio_variable', '')
        audio_path = self._get_variable_value(audio_var, context)
        operation = config.get('operation', 'stt')
        params = config.get('operation_params', {})
        output_var = config.get('output_variable', 'audio_result')
        
        try:
            if operation == 'stt':
                result = await self._speech_to_text(audio_path, params)
            elif operation == 'tts':
                text = params.get('text', '')
                result = await self._text_to_speech(text, params)
            elif operation == 'duration':
                result = await self._get_duration(audio_path)
            elif operation == 'format':
                result = audio_path
            else:
                result = audio_path
            
            return {output_var: result, 'status': 'completed'}
        except Exception as e:
            logger.error(f"Audio processing failed: {e}")
            return {output_var: '', 'error': str(e), 'status': 'failed'}
    
    async def _speech_to_text(self, audio_path: str, params: Dict) -> str:
        from apps.ai.utils.stt_service import STTService
        if not self.stt_service:
            self.stt_service = STTService()
        return await self.stt_service.transcribe(audio_path, params.get('language', 'zh-CN'))
    
    async def _text_to_speech(self, text: str, params: Dict) -> str:
        return f"TTS output for: {text}"
    
    async def _get_duration(self, audio_path: str) -> float:
        try:
            import wave
            with wave.open(audio_path, 'rb') as w:
                return w.getnframes() / w.getframerate()
        except:
            return 0.0


class MessageQueueProcessor(BaseNodeProcessor):
    """Message queue node for async messaging"""
    
    def __init__(self, node_type_code: str):
        super().__init__(node_type_code)
    
    def _get_config_schema(self) -> Dict[str, Any]:
        return {
            'queue_type': {
                'type': 'select',
                'required': True,
                'label': 'Queue Type',
                'options': [
                    {'value': 'redis', 'label': 'Redis'},
                    {'value': 'rabbitmq', 'label': 'RabbitMQ'},
                    {'value': 'kafka', 'label': 'Kafka'}
                ]
            },
            'queue_name': {
                'type': 'string',
                'required': True,
                'label': 'Queue Name',
                'placeholder': 'queue_name'
            },
            'operation': {
                'type': 'select',
                'required': True,
                'label': 'Operation',
                'options': [
                    {'value': 'publish', 'label': 'Publish Message'},
                    {'value': 'consume', 'label': 'Consume Message'}
                ]
            },
            'message': {
                'type': 'text',
                'required': False,
                'label': 'Message Content',
                'placeholder': 'JSON message'
            },
            'message_variable': {
                'type': 'string',
                'required': False,
                'label': 'Message Variable',
                'placeholder': 'Enter message variable name'
            },
            'output_variable': {
                'type': 'string',
                'required': True,
                'label': 'Output Variable',
                'default': 'queue_result'
            }
        }
    
    async def execute_async(self, config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        import redis
        
        queue_type = config.get('queue_type', 'redis')
        queue_name = config.get('queue_name', '')
        operation = config.get('operation', 'publish')
        message = config.get('message', '')
        message_var = config.get('message_variable', '')
        output_var = config.get('output_variable', 'queue_result')
        
        try:
            if queue_type == 'redis':
                r = redis.Redis(host='localhost', port=6379, db=0)
                
                if operation == 'publish':
                    msg = message or self._get_variable_value(message_var, context)
                    r.rpush(queue_name, msg)
                    return {output_var: {'status': 'published', 'queue': queue_name}, 'status': 'completed'}
                else:
                    msg = r.blpop(queue_name, timeout=1)
                    return {output_var: {'status': 'consumed', 'message': msg}, 'status': 'completed'}
            
            return {output_var: {'status': 'not_implemented'}, 'status': 'completed'}
        except Exception as e:
            logger.error(f"Message queue operation failed: {e}")
            return {output_var: {}, 'error': str(e), 'status': 'failed'}


class ScheduledTaskProcessor(BaseNodeProcessor):
    """Scheduled task node for time-based triggers"""
    
    def __init__(self, node_type_code: str):
        super().__init__(node_type_code)
    
    def _get_config_schema(self) -> Dict[str, Any]:
        return {
            'trigger_type': {
                'type': 'select',
                'required': True,
                'label': 'Trigger Type',
                'options': [
                    {'value': 'interval', 'label': 'Fixed Interval'},
                    {'value': 'cron', 'label': 'Cron Expression'},
                    {'value': 'specific_time', 'label': 'Specific Time'}
                ]
            },
            'interval': {
                'type': 'object',
                'required': False,
                'label': 'Interval',
                'fields': {
                    'value': {'type': 'number', 'label': 'Value'},
                    'unit': {'type': 'select', 'options': [
                        {'value': 'seconds', 'label': 'Seconds'},
                        {'value': 'minutes', 'label': 'Minutes'},
                        {'value': 'hours', 'label': 'Hours'},
                        {'value': 'days', 'label': 'Days'}
                    ]}
                }
            },
            'cron_expression': {
                'type': 'string',
                'required': False,
                'label': 'Cron Expression',
                'placeholder': '*/5 * * * *'
            },
            'specific_time': {
                'type': 'string',
                'required': False,
                'label': 'Specific Time',
                'placeholder': 'HH:MM:SS'
            },
            'output_variable': {
                'type': 'string',
                'required': True,
                'label': 'Output Variable',
                'default': 'schedule_result'
            }
        }
    
    async def execute_async(self, config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        trigger_type = config.get('trigger_type', 'interval')
        output_var = config.get('output_variable', 'schedule_result')
        
        now = datetime.now()
        
        if trigger_type == 'interval':
            interval = config.get('interval', {})
            value = interval.get('value', 60)
            unit = interval.get('unit', 'seconds')
            next_run = self._calculate_next_interval(now, value, unit)
        elif trigger_type == 'cron':
            cron_expr = config.get('cron_expression', '')
            next_run = self._calculate_next_cron(now, cron_expr)
        else:
            time_str = config.get('specific_time', '00:00:00')
            next_run = self._calculate_specific_time(now, time_str)
        
        return {
            output_var: {
                'triggered_at': now.isoformat(),
                'next_run': next_run.isoformat(),
                'trigger_type': trigger_type
            },
            'status': 'completed'
        }
    
    def _calculate_next_interval(self, now: datetime, value: int, unit: str) -> datetime:
        delta = timedelta(**{unit: value})
        return now + delta
    
    def _calculate_next_cron(self, now: datetime, cron_expr: str) -> datetime:
        return now + timedelta(hours=1)
    
    def _calculate_specific_time(self, now: datetime, time_str: str) -> datetime:
        try:
            hour, minute, second = map(int, time_str.split(':'))
            next_time = now.replace(hour=hour, minute=minute, second=second, microsecond=0)
            if next_time <= now:
                next_time += timedelta(days=1)
            return next_time
        except:
            return now + timedelta(days=1)


class WorkflowTriggerProcessor(BaseNodeProcessor):
    """Workflow trigger node for calling other workflows"""
    
    def __init__(self, node_type_code: str):
        super().__init__(node_type_code)
    
    def _get_config_schema(self) -> Dict[str, Any]:
        return {
            'workflow_id': {
                'type': 'string',
                'required': True,
                'label': 'Target Workflow',
                'placeholder': 'Select workflow to trigger'
            },
            'input_data': {
                'type': 'object',
                'required': False,
                'label': 'Input Data',
                'fields': {}
            },
            'execution_mode': {
                'type': 'select',
                'required': False,
                'label': 'Execution Mode',
                'options': [
                    {'value': 'sync', 'label': 'Synchronous'},
                    {'value': 'async', 'label': 'Asynchronous'}
                ],
                'default': 'sync'
            },
            'output_variable': {
                'type': 'string',
                'required': True,
                'label': 'Output Variable',
                'default': 'workflow_result'
            }
        }
    
    async def execute_async(self, config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        from apps.ai.services.workflow_service import WorkflowService
        
        workflow_id = config.get('workflow_id', '')
        input_data = config.get('input_data', {})
        mode = config.get('execution_mode', 'sync')
        output_var = config.get('output_variable', 'workflow_result')
        
        if not workflow_id:
            return {output_var: {}, 'error': 'Workflow ID required', 'status': 'failed'}
        
        try:
            service = WorkflowService()
            
            rendered_input = {}
            for key, value in input_data.items():
                rendered_input[key] = self._get_variable_value(str(value), context) if isinstance(value, str) else value
            
            if mode == 'async':
                loop = asyncio.get_event_loop()
                task = loop.create_task(service.execute_workflow_async(workflow_id, rendered_input))
                return {output_var: {'status': 'started', 'workflow_id': workflow_id}, 'status': 'completed'}
            else:
                result = await service.execute_workflow(workflow_id, rendered_input)
                return {output_var: result, 'status': 'completed'}
        except Exception as e:
            logger.error(f"Workflow trigger failed: {e}")
            return {output_var: {}, 'error': str(e), 'status': 'failed'}


class IteratorProcessor(BaseNodeProcessor):
    """Iterator node for sequential iteration over collections"""
    
    def __init__(self, node_type_code: str):
        super().__init__(node_type_code)
    
    def _get_config_schema(self) -> Dict[str, Any]:
        return {
            'collection_variable': {
                'type': 'string',
                'required': True,
                'label': 'Collection Variable',
                'placeholder': 'Enter collection variable name'
            },
            'loop_variable': {
                'type': 'string',
                'required': True,
                'label': 'Loop Variable Name',
                'default': 'item'
            },
            'index_variable': {
                'type': 'string',
                'required': False,
                'label': 'Index Variable Name',
                'default': 'index'
            },
            'max_iterations': {
                'type': 'number',
                'required': False,
                'label': 'Max Iterations',
                'default': 1000
            },
            'output_variable': {
                'type': 'string',
                'required': True,
                'label': 'Output Variable',
                'default': 'iteration_results'
            }
        }
    
    async def execute_async(self, config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        collection_var = config.get('collection_variable', '')
        collection = self._get_variable_value(collection_var, context)
        loop_var = config.get('loop_variable', 'item')
        index_var = config.get('index_variable', 'index')
        max_iter = config.get('max_iterations', 1000)
        output_var = config.get('output_variable', 'iteration_results')
        
        if not collection or not isinstance(collection, (list, dict, str)):
            return {output_var: [], 'status': 'completed'}
        
        results = []
        iteration_count = 0
        
        if isinstance(collection, str):
            collection = list(collection)
        
        if isinstance(collection, dict):
            iterator = collection.items()
        else:
            iterator = enumerate(collection)
        
        for idx, item in iterator:
            if iteration_count >= max_iter:
                break
            
            iteration_context = context.copy()
            iteration_context[loop_var] = item
            iteration_context[index_var] = idx
            
            loop_result = await self._execute_loop_body(config, iteration_context)
            results.append({
                'index': idx,
                'item': item,
                'result': loop_result
            })
            
            iteration_count += 1
        
        return {output_var: results, 'status': 'completed'}
    
    async def _execute_loop_body(self, config: Dict, context: Dict) -> Any:
        return context.get('item')


class ParameterAggregatorProcessor(BaseNodeProcessor):
    """Parameter aggregator node for collecting parameters"""
    
    def __init__(self, node_type_code: str):
        super().__init__(node_type_code)
    
    def _get_config_schema(self) -> Dict[str, Any]:
        return {
            'inputs': {
                'type': 'array',
                'required': True,
                'label': 'Input Parameters',
                'item_fields': {
                    'variable': {'type': 'string', 'label': 'Variable Name'},
                    'alias': {'type': 'string', 'label': 'Alias'}
                }
            },
            'output_structure': {
                'type': 'select',
                'required': False,
                'label': 'Output Structure',
                'options': [
                    {'value': 'object', 'label': 'Object'},
                    {'value': 'array', 'label': 'Array'}
                ],
                'default': 'object'
            },
            'output_variable': {
                'type': 'string',
                'required': True,
                'label': 'Output Variable',
                'default': 'aggregated_params'
            }
        }
    
    async def execute_async(self, config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        inputs = config.get('inputs', [])
        output_structure = config.get('output_structure', 'object')
        output_var = config.get('output_variable', 'aggregated_params')
        
        if output_structure == 'array':
            result = []
            for inp in inputs:
                value = self._get_variable_value(inp.get('variable', ''), context)
                result.append(value)
        else:
            result = {}
            for inp in inputs:
                value = self._get_variable_value(inp.get('variable', ''), context)
                alias = inp.get('alias', inp.get('variable', ''))
                result[alias] = value
        
        return {output_var: result, 'status': 'completed'}


class VariableAssignProcessor(BaseNodeProcessor):
    """Variable assignment node for setting variables"""
    
    def __init__(self, node_type_code: str):
        super().__init__(node_type_code)
    
    def _get_config_schema(self) -> Dict[str, Any]:
        return {
            'assignments': {
                'type': 'array',
                'required': True,
                'label': 'Variable Assignments',
                'item_fields': {
                    'variable': {'type': 'string', 'label': 'Variable Name'},
                    'value': {'type': 'text', 'label': 'Value'}
                }
            },
            'scope': {
                'type': 'select',
                'required': False,
                'label': 'Scope',
                'options': [
                    {'value': 'local', 'label': 'Local'},
                    {'value': 'global', 'label': 'Global'}
                ],
                'default': 'local'
            }
        }
    
    async def execute_async(self, config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        assignments = config.get('assignments', [])
        scope = config.get('scope', 'local')
        
        result_vars = {}
        
        for assignment in assignments:
            var_name = assignment.get('variable', '')
            value_str = assignment.get('value', '')
            value = self._get_variable_value(value_str, context)
            if value is None:
                value = value_str
            
            result_vars[var_name] = value
        
        if scope == 'global':
            context.update(result_vars)
        else:
            context.update(result_vars)
        
        return {**result_vars, 'status': 'completed'}


class ConversationHistoryProcessor(BaseNodeProcessor):
    """Conversation history node for managing chat history"""
    
    def __init__(self, node_type_code: str):
        super().__init__(node_type_code)
    
    def _get_config_schema(self) -> Dict[str, Any]:
        return {
            'action': {
                'type': 'select',
                'required': True,
                'label': 'Operation',
                'options': [
                    {'value': 'get', 'label': 'Get History'},
                    {'value': 'add', 'label': 'Add Message'},
                    {'value': 'clear', 'label': 'Clear History'},
                    {'value': 'count', 'label': 'Message Count'}
                ]
            },
            'conversation_id': {
                'type': 'string',
                'required': False,
                'label': 'Conversation ID',
                'placeholder': 'Enter conversation ID variable'
            },
            'message': {
                'type': 'text',
                'required': False,
                'label': 'Message Content',
                'placeholder': 'user: Hello\nassistant: Hi'
            },
            'message_variable': {
                'type': 'string',
                'required': False,
                'label': 'Message Variable',
                'placeholder': 'Enter message variable name'
            },
            'role': {
                'type': 'select',
                'required': False,
                'label': 'Role',
                'options': [
                    {'value': 'user', 'label': 'User'},
                    {'value': 'assistant', 'label': 'Assistant'},
                    {'value': 'system', 'label': 'System'}
                ]
            },
            'max_messages': {
                'type': 'number',
                'required': False,
                'label': 'Max Messages',
                'default': 20
            },
            'output_variable': {
                'type': 'string',
                'required': True,
                'label': 'Output Variable',
                'default': 'history'
            }
        }
    
    async def execute_async(self, config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        action = config.get('action', 'get')
        conv_id_var = config.get('conversation_id', 'conversation_id')
        message = config.get('message', '')
        message_var = config.get('message_variable', '')
        role = config.get('role', 'user')
        max_msgs = config.get('max_messages', 20)
        output_var = config.get('output_variable', 'history')
        
        conv_id = self._get_variable_value(conv_id_var, context) or 'default'
        
        history_key = f'chat_history_{conv_id}'
        history = context.get(history_key, [])
        
        if action == 'get':
            return {output_var: history[-max_msgs:], 'status': 'completed'}
        
        elif action == 'add':
            msg = message or self._get_variable_value(message_var, context)
            if msg:
                new_message = {'role': role, 'content': msg}
                history.append(new_message)
                context[history_key] = history[-max_msgs:]
            return {output_var: history, 'status': 'completed'}
        
        elif action == 'clear':
            context[history_key] = []
            return {output_var: [], 'status': 'completed'}
        
        elif action == 'count':
            return {output_var: len(history), 'status': 'completed'}
        
        return {output_var: history, 'status': 'completed'}


class CodeBlockProcessor(BaseNodeProcessor):
    """Code block node for executing custom code"""
    
    def __init__(self, node_type_code: str):
        super().__init__(node_type_code)
    
    def _get_config_schema(self) -> Dict[str, Any]:
        return {
            'code': {
                'type': 'text',
                'required': True,
                'label': 'Python Code',
                'placeholder': '# Enter your Python code here\n# Access input variables via context\nresult = input_data * 2'
            },
            'input_variables': {
                'type': 'array',
                'required': False,
                'label': 'Input Variables',
                'item_fields': {
                    'variable': {'type': 'string', 'label': 'Variable Name'}
                }
            },
            'output_variables': {
                'type': 'array',
                'required': False,
                'label': 'Output Variables',
                'item_fields': {
                    'variable': {'type': 'string', 'label': 'Variable Name'}
                }
            },
            'timeout': {
                'type': 'number',
                'required': False,
                'label': 'Timeout (seconds)',
                'default': 30
            },
            'sandboxed': {
                'type': 'boolean',
                'required': False,
                'label': 'Run in Sandbox',
                'default': True
            }
        }
    
    async def execute_async(self, config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        code = config.get('code', '')
        input_vars = config.get('input_variables', [])
        output_vars = config.get('output_variables', [])
        timeout = config.get('timeout', 30)
        sandboxed = config.get('sandboxed', True)
        
        try:
            local_context = {}
            for inp in input_vars:
                var_name = inp.get('variable', '')
                local_context[var_name] = self._get_variable_value(var_name, context)
            
            local_context['context'] = context
            
            if sandboxed:
                result = await self._execute_sandboxed(code, local_context, timeout)
            else:
                result = await self._execute_direct(code, local_context, timeout)
            
            output = {}
            for out in output_vars:
                var_name = out.get('variable', '')
                output[var_name] = local_context.get(var_name)
            
            return {**output, 'status': 'completed'}
        except Exception as e:
            logger.error(f"Code execution failed: {e}")
            return {'error': str(e), 'status': 'failed'}
    
    async def _execute_sandboxed(self, code: str, local_context: Dict, timeout: int) -> Any:
        import RestrictedPython
        
        byte_code = RestrictedPython.compile(code, '<string>', 'exec')
        if byte_code is None:
            raise SyntaxError("Invalid code syntax")
        
        restricted_globals = {
            '_print_': print,
            '_getattr_': getattr,
            '_setattr_': setattr,
            '_delattr_': delattr,
        }
        
        exec(byte_code, restricted_globals, local_context)
        return local_context
    
    async def _execute_direct(self, code: str, local_context: Dict, timeout: int) -> Any:
        exec(code, {}, local_context)
        return local_context


class ToolCallProcessor(BaseNodeProcessor):
    """Tool call node for invoking external tools"""
    
    def __init__(self, node_type_code: str):
        super().__init__(node_type_code)
    
    def _get_config_schema(self) -> Dict[str, Any]:
        return {
            'tool_name': {
                'type': 'string',
                'required': True,
                'label': 'Tool Name',
                'placeholder': 'Enter tool name'
            },
            'tool_params': {
                'type': 'object',
                'required': False,
                'label': 'Tool Parameters'
            },
            'input_variable': {
                'type': 'string',
                'required': False,
                'label': 'Input Variable',
                'placeholder': 'Enter input variable name'
            },
            'output_variable': {
                'type': 'string',
                'required': True,
                'label': 'Output Variable',
                'default': 'tool_result'
            }
        }
    
    async def execute_async(self, config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        tool_name = config.get('tool_name', '')
        tool_params = config.get('tool_params', {})
        input_var = config.get('input_variable', '')
        output_var = config.get('output_variable', 'tool_result')
        
        input_data = self._get_variable_value(input_var, context) if input_var else {}
        
        rendered_params = {}
        for key, value in tool_params.items():
            if isinstance(value, str):
                rendered_value = self._get_variable_value(value, context)
                rendered_params[key] = rendered_value if rendered_value is not None else value
            else:
                rendered_params[key] = value
        
        try:
            result = await self._call_tool(tool_name, rendered_params, input_data)
            return {output_var: result, 'status': 'completed'}
        except Exception as e:
            logger.error(f"Tool call failed: {e}")
            return {output_var: {}, 'error': str(e), 'status': 'failed'}
    
    async def _call_tool(self, tool_name: str, params: Dict, input_data: Any) -> Any:
        available_tools = {
            'calculator': self._tool_calculator,
            'date_time': self._tool_datetime,
            'url_encoder': self._tool_url_encoder,
            'hash': self._tool_hash,
            'random': self._tool_random,
        }
        
        if tool_name in available_tools:
            return await available_tools[tool_name](params, input_data)
        else:
            raise ValueError(f"Unknown tool: {tool_name}")
    
    async def _tool_calculator(self, params: Dict, input_data: Any) -> Any:
        expression = params.get('expression', '')
        try:
            result = eval(expression)
            return {'result': result}
        except:
            return {'error': 'Invalid expression'}
    
    async def _tool_datetime(self, params: Dict, input_data: Any) -> Any:
        from datetime import datetime
        format_str = params.get('format', '%Y-%m-%d %H:%M:%S')
        return {'datetime': datetime.now().strftime(format_str)}
    
    async def _tool_url_encoder(self, params: Dict, input_data: Any) -> Any:
        text = params.get('text', '')
        return {'encoded': quote(text)}
    
    async def _tool_hash(self, params: Dict, input_data: Any) -> Any:
        text = params.get('text', '')
        algorithm = params.get('algorithm', 'md5')
        if algorithm == 'md5':
            return {'hash': hashlib.md5(text.encode()).hexdigest()}
        elif algorithm == 'sha256':
            return {'hash': hashlib.sha256(text.encode()).hexdigest()}
        return {}
    
    async def _tool_random(self, params: Dict, input_data: Any) -> Any:
        import random
        min_val = params.get('min', 0)
        max_val = params.get('max', 100)
        return {'random': random.randint(min_val, max_val)}


def register_complete_nodes():
    """Register all complete node processors"""
    registry = NodeProcessorRegistry.get_instance()
    
    processors = [
        ('advanced_text_processing', TextProcessingProcessor, 'Advanced Text Processing'),
        ('document_extractor', DocumentExtractorProcessor, 'Document Extractor'),
        ('http_request', HttpRequestProcessor, 'HTTP Request'),
        ('database', DatabaseProcessor, 'Database'),
        ('template', TemplateProcessor, 'Template'),
        ('sentiment_analysis', SentimentAnalysisProcessor, 'Sentiment Analysis'),
        ('image_processing', ImageProcessor, 'Image Processing'),
        ('audio_processing', AudioProcessor, 'Audio Processing'),
        ('message_queue', MessageQueueProcessor, 'Message Queue'),
        ('scheduled_task', ScheduledTaskProcessor, 'Scheduled Task'),
        ('workflow_trigger', WorkflowTriggerProcessor, 'Workflow Trigger'),
        ('iterator', IteratorProcessor, 'Iterator'),
        ('parameter_aggregator', ParameterAggregatorProcessor, 'Parameter Aggregator'),
        ('variable_assign', VariableAssignProcessor, 'Variable Assign'),
        ('conversation_history', ConversationHistoryProcessor, 'Conversation History'),
        ('code_block', CodeBlockProcessor, 'Code Block'),
        ('tool_call', ToolCallProcessor, 'Tool Call'),
    ]
    
    for code, processor_class, name in processors:
        processor = processor_class(code)
        registry.register(code, processor)
        registry.register(name, processor)
    
    logger.info(f"Registered {len(processors)} complete node processors")
