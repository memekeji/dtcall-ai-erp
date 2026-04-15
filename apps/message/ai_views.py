import logging
import json
from django.http import JsonResponse
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from apps.message.models import Message
from apps.ai.utils.ai_client import AIClient

logger = logging.getLogger(__name__)

class MessageAIAssistantView(LoginRequiredMixin, View):
    """消息AI智能助手"""
    
    def post(self, request, message_id):
        try:
            message = Message.objects.get(id=message_id)
            
            # 检查是否有权限查看该消息 (发送者或接收者)
            is_sender = message.sender == request.user
            is_receiver = message.receivers.filter(id=request.user.id).exists()
            
            if not (is_sender or is_receiver):
                return JsonResponse({'code': 1, 'msg': '无权限访问该消息'})
                
            # 如果已经有处理结果且未要求强制刷新
            force_refresh = request.POST.get('force_refresh', 'false') == 'true'
            if not force_refresh and (message.ai_summary or message.ai_suggested_replies):
                return JsonResponse({
                    'code': 0,
                    'msg': 'success',
                    'data': {
                        'summary': message.ai_summary,
                        'suggested_replies': message.ai_suggested_replies
                    }
                })
                
            # 如果消息太短，不需要摘要
            if len(message.content) < 50:
                return JsonResponse({'code': 1, 'msg': '消息过短，无需AI分析'})
                
            # 调用AI分析
            ai_client = AIClient()
            prompt = f"""
请分析以下消息内容，并提供：
1. 简短摘要（不超过50字）
2. 3个针对性的简短快捷回复建议（按JSON数组格式返回，不要任何其他说明文字）

消息标题: {message.title}
消息内容: {message.content}

输出格式示例：
摘要：这里是摘要内容
回复建议：["好的，我马上处理", "收到，稍后回复", "这个没问题"]
"""
            response = ai_client.generate(prompt)
            
            summary = ""
            suggested_replies = []
            
            try:
                # 简单解析
                if "回复建议：" in response:
                    parts = response.split("回复建议：")
                    summary = parts[0].replace("摘要：", "").strip()
                    reply_str = parts[1].strip()
                    # 尝试解析JSON
                    suggested_replies = json.loads(reply_str)
                else:
                    summary = response[:100]
            except Exception as e:
                logger.error(f"解析AI回复建议失败: {str(e)}")
                
            message.ai_summary = summary
            if suggested_replies:
                message.ai_suggested_replies = suggested_replies
            message.save()
            
            return JsonResponse({
                'code': 0,
                'msg': '分析完成',
                'data': {
                    'summary': message.ai_summary,
                    'suggested_replies': message.ai_suggested_replies
                }
            })
            
        except Message.DoesNotExist:
            return JsonResponse({'code': 1, 'msg': '消息不存在'})
        except Exception as e:
            logger.error(f"消息AI分析失败: {str(e)}")
            return JsonResponse({'code': 1, 'msg': f'分析失败: {str(e)}'})
