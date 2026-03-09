import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dtcall.settings')
import django
django.setup()

from apps.ai.utils.ai_client import AIClient

print('测试 AIClient(model_config_id=3):')
try:
    client = AIClient(model_config_id=3)
    print('  客户端创建成功')
    
    messages = [{'role': 'user', 'content': '你好'}]
    result = client.chat_completion(messages)
    print('  成功! 响应:', result[:50])
except Exception as e:
    import traceback
    print('  错误:', str(e)[:150])
    traceback.print_exc()
