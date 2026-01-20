"""
文件操作节点处理器
"""

import os
import shutil
import json
from .base_processor import BaseNodeProcessor, NodeProcessorRegistry


@NodeProcessorRegistry.register('file_operation')
class FileOperationProcessor(BaseNodeProcessor):
    """文件操作节点处理器"""
    
    @classmethod
    def get_display_name(cls):
        return "文件操作节点"
    
    @classmethod
    def get_icon(cls):
        return "layui-icon-file"
    
    @classmethod
    def get_description(cls):
        return "执行文件系统操作"
    
    def _get_config_schema(self) -> dict:
        """获取文件操作节点的配置模式"""
        return {
            'operation_type': {
                'type': 'string',
                'required': True,
                'label': '操作类型',
                'options': [
                    {'value': 'create_dir', 'label': '创建目录'},
                    {'value': 'delete_dir', 'label': '删除目录'},
                    {'value': 'upload_file', 'label': '上传文件'},
                    {'value': 'download_file', 'label': '下载文件'},
                    {'value': 'copy_file', 'label': '复制文件'},
                    {'value': 'move_file', 'label': '移动文件'},
                    {'value': 'delete_file', 'label': '删除文件'},
                    {'value': 'read_file', 'label': '读取文件'},
                    {'value': 'write_file', 'label': '写入文件'}
                ],
                'description': '选择要执行的文件操作类型'
            },
            'source_path': {
                'type': 'string',
                'required': False,
                'label': '源路径',
                'description': '源文件或目录路径',
                'depends_on': {
                    'operation_type': ['copy_file', 'move_file', 'delete_file', 'read_file', 'download_file']
                }
            },
            'target_path': {
                'type': 'string',
                'required': False,
                'label': '目标路径',
                'description': '目标文件或目录路径',
                'depends_on': {
                    'operation_type': ['create_dir', 'copy_file', 'move_file', 'write_file']
                }
            },
            'file_content': {
                'type': 'string',
                'required': False,
                'label': '文件内容',
                'description': '要写入的文件内容',
                'depends_on': {'operation_type': 'write_file'}
            },
            'encoding': {
                'type': 'string',
                'required': False,
                'label': '编码格式',
                'default': 'utf-8',
                'options': [
                    {'value': 'utf-8', 'label': 'UTF-8'},
                    {'value': 'gbk', 'label': 'GBK'},
                    {'value': 'ascii', 'label': 'ASCII'}
                ],
                'description': '文件编码格式'
            },
            'recursive': {
                'type': 'boolean',
                'required': False,
                'label': '递归操作',
                'default': False,
                'description': '是否递归处理子目录'
            },
            'overwrite': {
                'type': 'boolean',
                'required': False,
                'label': '覆盖文件',
                'default': False,
                'description': '是否覆盖已存在的文件'
            },
            'timeout': {
                'type': 'number',
                'required': False,
                'label': '超时时间',
                'default': 30,
                'min': 1,
                'max': 300,
                'description': '操作超时时间（秒）'
            }
        }
    
    def execute(self, config: dict, context: dict) -> dict:
        """执行文件操作节点逻辑"""
        operation_type = config.get('operation_type', '')
        source_path = config.get('source_path', '')
        target_path = config.get('target_path', '')
        encoding = config.get('encoding', 'utf-8')
        recursive = config.get('recursive', False)
        overwrite = config.get('overwrite', False)
        
        # 替换路径中的变量
        source_path = self._replace_variables(source_path, context)
        target_path = self._replace_variables(target_path, context)
        
        result = {
            'operation_type': operation_type,
            'success': False,
            'message': '',
            'data': None
        }
        
        try:
            if operation_type == 'create_dir':
                self._create_directory(target_path, recursive)
                result['success'] = True
                result['message'] = f"目录创建成功: {target_path}"
                
            elif operation_type == 'delete_dir':
                self._delete_directory(source_path, recursive)
                result['success'] = True
                result['message'] = f"目录删除成功: {source_path}"
                
            elif operation_type == 'copy_file':
                self._copy_file(source_path, target_path, overwrite)
                result['success'] = True
                result['message'] = f"文件复制成功: {source_path} -> {target_path}"
                
            elif operation_type == 'move_file':
                self._move_file(source_path, target_path, overwrite)
                result['success'] = True
                result['message'] = f"文件移动成功: {source_path} -> {target_path}"
                
            elif operation_type == 'delete_file':
                self._delete_file(source_path)
                result['success'] = True
                result['message'] = f"文件删除成功: {source_path}"
                
            elif operation_type == 'read_file':
                content = self._read_file(source_path, encoding)
                result['success'] = True
                result['message'] = f"文件读取成功: {source_path}"
                result['data'] = content
                
            elif operation_type == 'write_file':
                file_content = config.get('file_content', '')
                file_content = self._replace_variables(file_content, context)
                self._write_file(target_path, file_content, encoding, overwrite)
                result['success'] = True
                result['message'] = f"文件写入成功: {target_path}"
                
            else:
                result['message'] = f"不支持的操作类型: {operation_type}"
                
        except Exception as e:
            result['message'] = f"文件操作失败: {str(e)}"
        
        return result
    
    def _create_directory(self, path: str, recursive: bool = False):
        """创建目录"""
        if recursive:
            os.makedirs(path, exist_ok=True)
        else:
            os.mkdir(path)
    
    def _delete_directory(self, path: str, recursive: bool = False):
        """删除目录"""
        if recursive:
            shutil.rmtree(path)
        else:
            os.rmdir(path)
    
    def _copy_file(self, source: str, target: str, overwrite: bool = False):
        """复制文件"""
        if os.path.exists(target) and not overwrite:
            raise Exception(f"目标文件已存在: {target}")
        shutil.copy2(source, target)
    
    def _move_file(self, source: str, target: str, overwrite: bool = False):
        """移动文件"""
        if os.path.exists(target) and not overwrite:
            raise Exception(f"目标文件已存在: {target}")
        shutil.move(source, target)
    
    def _delete_file(self, path: str):
        """删除文件"""
        os.remove(path)
    
    def _read_file(self, path: str, encoding: str = 'utf-8') -> str:
        """读取文件内容"""
        with open(path, 'r', encoding=encoding) as f:
            return f.read()
    
    def _write_file(self, path: str, content: str, encoding: str = 'utf-8', overwrite: bool = False):
        """写入文件内容"""
        if os.path.exists(path) and not overwrite:
            raise Exception(f"文件已存在: {path}")
        
        # 确保目录存在
        os.makedirs(os.path.dirname(path), exist_ok=True)
        
        with open(path, 'w', encoding=encoding) as f:
            f.write(content)
    
    def _replace_variables(self, text: str, context: dict) -> str:
        """替换文本中的变量占位符"""
        if not isinstance(text, str):
            return text
        
        for key, value in context.items():
            placeholder = f'{{{{{key}}}}}'
            text = text.replace(placeholder, str(value))
        
        return text


@NodeProcessorRegistry.register('code_execution')
class CodeExecutionProcessor(BaseNodeProcessor):
    """代码执行节点处理器"""
    
    @classmethod
    def get_display_name(cls):
        return "代码执行节点"
    
    @classmethod
    def get_icon(cls):
        return "layui-icon-code"
    
    @classmethod
    def get_description(cls):
        return "执行自定义代码逻辑"
    
    def _get_config_schema(self) -> dict:
        """获取代码执行节点的配置模式"""
        return {
            'language': {
                'type': 'string',
                'required': True,
                'label': '编程语言',
                'options': [
                    {'value': 'python', 'label': 'Python'},
                    {'value': 'javascript', 'label': 'JavaScript'},
                    {'value': 'shell', 'label': 'Shell脚本'},
                    {'value': 'sql', 'label': 'SQL'}
                ],
                'description': '选择要执行的代码语言'
            },
            'code_content': {
                'type': 'string',
                'required': True,
                'label': '代码内容',
                'description': '要执行的代码内容',
                'multiline': True,
                'rows': 10
            },
            'timeout': {
                'type': 'number',
                'required': False,
                'label': '超时时间',
                'default': 30,
                'min': 1,
                'max': 300,
                'description': '代码执行超时时间（秒）'
            },
            'capture_output': {
                'type': 'boolean',
                'required': False,
                'label': '捕获输出',
                'default': True,
                'description': '是否捕获代码执行输出'
            },
            'environment_vars': {
                'type': 'object',
                'required': False,
                'label': '环境变量',
                'default': {},
                'description': '代码执行时的环境变量'
            }
        }
    
    def execute(self, config: dict, context: dict) -> dict:
        """执行代码执行节点逻辑"""
        language = config.get('language', 'python')
        code_content = config.get('code_content', '')
        timeout = config.get('timeout', 30)
        capture_output = config.get('capture_output', True)
        environment_vars = config.get('environment_vars', {})
        
        # 替换代码中的变量
        code_content = self._replace_variables(code_content, context)
        
        result = {
            'language': language,
            'success': False,
            'output': '',
            'error': '',
            'execution_time': 0
        }
        
        try:
            import time
            start_time = time.time()
            
            if language == 'python':
                output = self._execute_python_code(code_content, context, environment_vars)
                result['success'] = True
                result['output'] = output
                
            elif language == 'javascript':
                output = self._execute_javascript_code(code_content, context, environment_vars)
                result['success'] = True
                result['output'] = output
                
            elif language == 'shell':
                output = self._execute_shell_code(code_content, context, environment_vars, timeout)
                result['success'] = True
                result['output'] = output
                
            elif language == 'sql':
                output = self._execute_sql_code(code_content, context, environment_vars)
                result['success'] = True
                result['output'] = output
                
            else:
                result['error'] = f"不支持的语言: {language}"
            
            result['execution_time'] = time.time() - start_time
            
        except Exception as e:
            result['error'] = f"代码执行失败: {str(e)}"
        
        return result
    
    def _execute_python_code(self, code: str, context: dict, env_vars: dict) -> str:
        """执行Python代码"""
        # 创建安全的执行环境
        safe_globals = {
            '__builtins__': {
                'print': print,
                'len': len,
                'str': str,
                'int': int,
                'float': float,
                'list': list,
                'dict': dict,
                'tuple': tuple,
                'set': set,
                'bool': bool,
                'type': type,
                'range': range,
                'enumerate': enumerate,
                'zip': zip,
                'min': min,
                'max': max,
                'sum': sum,
                'abs': abs,
                'round': round,
                'sorted': sorted,
                'reversed': reversed
            }
        }
        
        # 添加上下文变量
        safe_globals.update(context)
        safe_globals.update(env_vars)
        
        # 执行代码
        try:
            exec(code, safe_globals)
            return "代码执行成功"
        except Exception as e:
            raise Exception(f"Python代码执行错误: {str(e)}")
    
    def _execute_javascript_code(self, code: str, context: dict, env_vars: dict) -> str:
        """执行JavaScript代码"""
        # 这里可以集成Node.js或浏览器环境
        # 目前返回占位符
        return "JavaScript执行环境待实现"
    
    def _execute_shell_code(self, code: str, context: dict, env_vars: dict, timeout: int) -> str:
        """执行Shell脚本"""
        import subprocess
        
        try:
            result = subprocess.run(
                code,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                env={**os.environ, **env_vars}
            )
            
            if result.returncode == 0:
                return result.stdout
            else:
                raise Exception(f"Shell执行失败: {result.stderr}")
                
        except subprocess.TimeoutExpired:
            raise Exception("Shell执行超时")
        except Exception as e:
            raise Exception(f"Shell执行错误: {str(e)}")
    
    def _execute_sql_code(self, code: str, context: dict, env_vars: dict) -> str:
        """执行SQL代码"""
        # 这里可以集成数据库连接
        # 目前返回占位符
        return "SQL执行环境待实现"