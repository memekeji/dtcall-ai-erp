import logging
from django.http import JsonResponse
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from apps.disk.models import DiskFile
from apps.ai.utils.ai_client import AIClient
import os
import PyPDF2
from docx import Document

logger = logging.getLogger(__name__)

class FileAIAssistantView(LoginRequiredMixin, View):
    """网盘文件AI智能助手"""
    
    def extract_text(self, file_path, file_ext):
        """简单文本提取"""
        text = ""
        try:
            if not os.path.exists(file_path):
                return text
                
            if file_ext in ['.txt', '.md', '.csv']:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    text = f.read(10000)  # 读取前10000个字符
            elif file_ext == '.pdf':
                with open(file_path, 'rb') as f:
                    reader = PyPDF2.PdfReader(f)
                    for i in range(min(5, len(reader.pages))): # 读取前5页
                        text += reader.pages[i].extract_text()
            elif file_ext == '.docx':
                doc = Document(file_path)
                for i, para in enumerate(doc.paragraphs):
                    if i > 100: break # 读取前100段
                    text += para.text + "\n"
        except Exception as e:
            logger.error(f"提取文本失败: {str(e)}")
            
        return text[:10000] # 限制最大长度
    
    def post(self, request, file_id):
        try:
            disk_file = DiskFile.objects.get(id=file_id, owner=request.user)
            
            # 如果已经有AI处理结果，直接返回
            if disk_file.ai_status == 2 and disk_file.ai_summary:
                return JsonResponse({
                    'code': 0,
                    'msg': 'success',
                    'data': {
                        'summary': disk_file.ai_summary,
                        'tags': disk_file.ai_tags
                    }
                })
                
            # 提取文件内容
            file_ext = disk_file.file_ext.lower()
            if file_ext not in ['.txt', '.md', '.csv', '.pdf', '.docx']:
                return JsonResponse({'code': 1, 'msg': '当前文件类型不支持AI分析'})
                
            # 假设文件存储在 MEDIA_ROOT 下的 file.file.name
            file_path = disk_file.file.path if hasattr(disk_file, 'file') and disk_file.file else ""
            if not file_path:
                return JsonResponse({'code': 1, 'msg': '找不到文件路径'})
                
            text = self.extract_text(file_path, file_ext)
            if not text.strip():
                return JsonResponse({'code': 1, 'msg': '无法提取文件文本内容'})
                
            disk_file.ai_status = 1
            disk_file.save()
            
            # 调用AI分析
            ai_client = AIClient()
            prompt = f"""
请分析以下文件内容，并提供：
1. 一段简短的摘要（不超过200字）
2. 3-5个核心标签（用逗号分隔）

文件内容片段：
{text}
"""
            response = ai_client.generate(prompt)
            
            # 简单解析返回结果
            summary = response
            tags = "文档,资料"
            if "标签" in response:
                parts = response.split("标签")
                summary = parts[0].replace("摘要", "").strip(":： \n")
                tags = parts[1].strip(":： \n")
            
            disk_file.ai_summary = summary
            disk_file.ai_tags = tags
            disk_file.ai_content_text = text
            disk_file.ai_status = 2
            disk_file.save()
            
            return JsonResponse({
                'code': 0,
                'msg': '分析完成',
                'data': {
                    'summary': summary,
                    'tags': tags
                }
            })
            
        except DiskFile.DoesNotExist:
            return JsonResponse({'code': 1, 'msg': '文件不存在或无权限'})
        except Exception as e:
            logger.error(f"文件AI分析失败: {str(e)}")
            if 'disk_file' in locals():
                disk_file.ai_status = 3
                disk_file.save()
            return JsonResponse({'code': 1, 'msg': f'分析失败: {str(e)}'})
