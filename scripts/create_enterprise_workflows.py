#!/usr/bin/env python
"""
批量创建20个企业级AI工作流模板
运行方式: python scripts/create_enterprise_workflows.py
"""

import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dtcall.settings')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
django.setup()

from django.contrib.auth import get_user_model
from apps.ai.models import AIWorkflow, WorkflowNode, WorkflowConnection

User = get_user_model()

def get_or_create_admin_user():
    try:
        user = User.objects.filter(username='admin').first()
        if not user:
            user = User.objects.create_superuser(
                username='admin', email='admin@dtcall.com', password='admin123'
            )
        return user
    except:
        return User.objects.first()

def create_workflow(workflows_data):
    user = get_or_create_admin_user()
    created_workflows = []
    
    for data in workflows_data:
        print(f"创建工作流: {data['name']}...")
        
        workflow = AIWorkflow.objects.create(
            name=data['name'],
            description=data['description'],
            status='published',
            is_public=True,
            owner=user,
            created_by=user,
        )
        
        nodes = {}
        for node_data in data['nodes']:
            node = WorkflowNode.objects.create(
                workflow=workflow,
                name=node_data['name'],
                node_type=node_data['node_type'],
                position_x=node_data['position_x'],
                position_y=node_data['position_y'],
                config=node_data.get('config', {})
            )
            nodes[node_data['id']] = node
        
        for conn_data in data['connections']:
            WorkflowConnection.objects.create(
                workflow=workflow,
                source_node=nodes[conn_data['source']],
                target_node=nodes[conn_data['target']],
                source_handle=conn_data.get('source_handle', 'output'),
                target_handle=conn_data.get('target_handle', 'input'),
                config=conn_data.get('config', {})
            )
        
        created_workflows.append(workflow)
        print(f"  ✓ 创建完成 ({len(data['nodes'])} 节点, {len(data['connections'])} 连接)")
    
    return created_workflows

def get_enterprise_workflows():
    return [
        {
            'name': '智能客服系统',
            'description': '基于AI的智能客服工作流，支持意图识别、情感分析、知识检索和自动回复，提升客户服务效率和质量。',
            'nodes': [
                {'id': 'start', 'name': '开始', 'node_type': 'data_input', 'position_x': 100, 'position_y': 250, 'config': {'trigger_type': 'webhook', 'input_config': {'input_type': 'json', 'output_variable': 'user_input'}}},
                {'id': 'intent', 'name': '意图识别', 'node_type': 'intent_recognition', 'position_x': 280, 'position_y': 150, 'config': {'model': 'general', 'output_variable': 'intent'}},
                {'id': 'sentiment', 'name': '情感分析', 'node_type': 'sentiment_analysis', 'position_x': 280, 'position_y': 350, 'config': {'analysis_type': 'fine', 'output_variable': 'sentiment'}},
                {'id': 'condition', 'name': '情感判断', 'node_type': 'condition', 'position_x': 460, 'position_y': 250, 'config': {'condition': '${sentiment.sentiment} == "negative"', 'true_output': 'escalate', 'false_output': 'normal'}},
                {'id': 'knowledge', 'name': '知识检索', 'node_type': 'knowledge_retrieval', 'position_x': 640, 'position_y': 150, 'config': {'query_variable': 'user_input', 'top_k': 5, 'output_variable': 'knowledge'}},
                {'id': 'ai_reply', 'name': 'AI生成回复', 'node_type': 'ai_generation', 'position_x': 640, 'position_y': 350, 'config': {'prompt': '根据以下知识回答用户问题', 'output_variable': 'ai_response', 'input_data': {'knowledge_content': '${knowledge.content}', 'user_question': '${user_input}'}}},
                {'id': 'notify', 'name': '通知客服', 'node_type': 'notification', 'position_x': 820, 'position_y': 250, 'config': {'channel': 'email', 'title': '高优先级工单', 'message': '用户问题：${user_input}'}},
                {'id': 'output', 'name': '输出回复', 'node_type': 'data_output', 'position_x': 1000, 'position_y': 250, 'config': {'output_data': '${ai_response}', 'save_result': True}},
            ],
            'connections': [
                {'source': 'start', 'target': 'intent'}, {'source': 'start', 'target': 'sentiment'},
                {'source': 'intent', 'target': 'condition'}, {'source': 'sentiment', 'target': 'condition'},
                {'source': 'condition', 'target': 'knowledge', 'config': {'condition': 'normal'}},
                {'source': 'condition', 'target': 'ai_reply', 'config': {'condition': 'normal'}},
                {'source': 'condition', 'target': 'notify', 'config': {'condition': 'escalate'}},
                {'source': 'knowledge', 'target': 'ai_reply'}, {'source': 'ai_reply', 'target': 'output'},
                {'source': 'notify', 'target': 'output'},
            ]
        },
        {
            'name': '文档智能问答',
            'description': '上传文档后自动提取内容，支持基于文档内容的智能问答，适用于企业内部知识管理。',
            'nodes': [
                {'id': 'start', 'name': '开始', 'node_type': 'data_input', 'position_x': 100, 'position_y': 250, 'config': {'trigger_type': 'manual', 'input_config': {'input_type': 'file', 'output_variable': 'document'}}},
                {'id': 'extract', 'name': '文档提取', 'node_type': 'document_extractor', 'position_x': 280, 'position_y': 250, 'config': {'file_type': 'pdf', 'extraction_method': 'text', 'output_variable': 'content'}},
                {'id': 'ai_answer', 'name': 'AI问答', 'node_type': 'ai_generation', 'position_x': 460, 'position_y': 250, 'config': {'prompt': '根据文档内容回答问题', 'output_variable': 'answer'}},
                {'id': 'output', 'name': '输出答案', 'node_type': 'data_output', 'position_x': 640, 'position_y': 250, 'config': {'output_data': '${answer}', 'save_result': True}},
            ],
            'connections': [
                {'source': 'start', 'target': 'extract'}, {'source': 'extract', 'target': 'ai_answer'},
                {'source': 'ai_answer', 'target': 'output'},
            ]
        },
        {
            'name': '销售线索评分',
            'description': '自动分析销售线索，基于多维度评分模型进行线索分级，帮助销售团队优先处理高价值潜在客户。',
            'nodes': [
                {'id': 'start', 'name': '开始', 'node_type': 'data_input', 'position_x': 100, 'position_y': 250, 'config': {'trigger_type': 'webhook', 'input_config': {'input_type': 'json', 'output_variable': 'lead_data'}}},
                {'id': 'classify', 'name': '线索分类', 'node_type': 'ai_classify', 'position_x': 280, 'position_y': 150, 'config': {'categories': [{'name': '企业客户', 'description': '有明确企业背景'}, {'name': '个人客户', 'description': '个人需求'}], 'output_variable': 'lead_type'}},
                {'id': 'sentiment', 'name': '意向分析', 'node_type': 'sentiment_analysis', 'position_x': 280, 'position_y': 350, 'config': {'analysis_type': 'fine', 'output_variable': 'purchase_intent'}},
                {'id': 'score', 'name': '评分计算', 'node_type': 'ai_classify', 'position_x': 460, 'position_y': 250, 'config': {'categories': [{'name': 'A级', 'description': '高价值'}, {'name': 'B级', 'description': '中等价值'}, {'name': 'C级', 'description': '低价值'}], 'output_variable': 'lead_score'}},
                {'id': 'notify', 'name': '通知销售', 'node_type': 'notification', 'position_x': 640, 'position_y': 100, 'config': {'channel': 'email', 'title': '高价值线索', 'message': '新线索评分A级，请及时跟进！'}},
                {'id': 'output', 'name': '输出结果', 'node_type': 'data_output', 'position_x': 820, 'position_y': 250, 'config': {'output_data': {'score': '${lead_score}', 'type': '${lead_type}'}, 'save_result': True}},
            ],
            'connections': [
                {'source': 'start', 'target': 'classify'}, {'source': 'start', 'target': 'sentiment'},
                {'source': 'classify', 'target': 'score'}, {'source': 'sentiment', 'target': 'score'},
                {'source': 'score', 'target': 'notify', 'config': {'condition': 'contains "A级"'}},
                {'source': 'score', 'target': 'output'},
            ]
        },
        {
            'name': '合同风险检测',
            'description': '自动分析合同文本，识别潜在法律风险和不利条款，生成风险报告和改进建议。',
            'nodes': [
                {'id': 'start', 'name': '开始', 'node_type': 'data_input', 'position_x': 100, 'position_y': 250, 'config': {'trigger_type': 'manual', 'input_config': {'input_type': 'file', 'output_variable': 'contract'}}},
                {'id': 'extract', 'name': '文档提取', 'node_type': 'document_extractor', 'position_x': 280, 'position_y': 250, 'config': {'file_type': 'pdf', 'extraction_method': 'text', 'output_variable': 'content'}},
                {'id': 'ai_analysis', 'name': 'AI风险分析', 'node_type': 'ai_generation', 'position_x': 460, 'position_y': 150, 'config': {'prompt': '分析合同文本，识别法律风险', 'output_variable': 'risk_analysis'}},
                {'id': 'classify', 'name': '风险分类', 'node_type': 'ai_classify', 'position_x': 460, 'position_y': 350, 'config': {'categories': [{'name': '高风险', 'description': '需要立即修改'}, {'name': '中风险', 'description': '建议协商'}, {'name': '低风险', 'description': '可接受'}], 'output_variable': 'risk_level'}},
                {'id': 'output', 'name': '输出报告', 'node_type': 'data_output', 'position_x': 640, 'position_y': 250, 'config': {'output_data': {'level': '${risk_level}', 'analysis': '${risk_analysis}'}, 'save_result': True}},
            ],
            'connections': [
                {'source': 'start', 'target': 'extract'}, {'source': 'extract', 'target': 'ai_analysis'},
                {'source': 'extract', 'target': 'classify'}, {'source': 'ai_analysis', 'target': 'output'},
                {'source': 'classify', 'target': 'output'},
            ]
        },
        {
            'name': '会议纪要生成',
            'description': '自动转录会议音频，提取关键信息、决策事项和待办任务，生成结构化的会议纪要。',
            'nodes': [
                {'id': 'start', 'name': '开始', 'node_type': 'data_input', 'position_x': 100, 'position_y': 250, 'config': {'trigger_type': 'manual', 'input_config': {'input_type': 'file', 'output_variable': 'audio_file'}}},
                {'id': 'transcribe', 'name': '语音转文字', 'node_type': 'audio_processing', 'position_x': 280, 'position_y': 250, 'config': {'operation': 'stt', 'audio_variable': 'audio_file', 'output_variable': 'transcript'}},
                {'id': 'ai_summary', 'name': 'AI总结', 'node_type': 'ai_generation', 'position_x': 460, 'position_y': 150, 'config': {'prompt': '生成会议纪要，包括讨论要点和决策事项', 'output_variable': 'summary'}},
                {'id': 'extract_tasks', 'name': '提取待办', 'node_type': 'ai_generation', 'position_x': 460, 'position_y': 350, 'config': {'prompt': '从会议记录中提取所有待办任务', 'output_variable': 'action_items'}},
                {'id': 'output', 'name': '输出纪要', 'node_type': 'data_output', 'position_x': 640, 'position_y': 250, 'config': {'output_data': {'summary': '${summary}', 'tasks': '${action_items}'}, 'save_result': True}},
            ],
            'connections': [
                {'source': 'start', 'target': 'transcribe'}, {'source': 'transcribe', 'target': 'ai_summary'},
                {'source': 'transcribe', 'target': 'extract_tasks'}, {'source': 'ai_summary', 'target': 'output'},
                {'source': 'extract_tasks', 'target': 'output'},
            ]
        },
        {
            'name': '客户情感洞察',
            'description': '批量分析客户反馈和评论，识别情感趋势和关键话题，生成客户洞察报告。',
            'nodes': [
                {'id': 'start', 'name': '开始', 'node_type': 'data_input', 'position_x': 100, 'position_y': 250, 'config': {'trigger_type': 'scheduled_task', 'input_config': {'input_type': 'json', 'output_variable': 'feedback_data'}}},
                {'id': 'sentiment', 'name': '情感分析', 'node_type': 'sentiment_analysis', 'position_x': 280, 'position_y': 250, 'config': {'analysis_type': 'emotion', 'output_variable': 'emotion_result'}},
                {'id': 'ai_report', 'name': '生成报告', 'node_type': 'ai_generation', 'position_x': 460, 'position_y': 250, 'config': {'prompt': '基于情感分析结果生成客户洞察报告', 'output_variable': 'report'}},
                {'id': 'output', 'name': '输出报告', 'node_type': 'data_output', 'position_x': 640, 'position_y': 250, 'config': {'output_data': {'report': '${report}', 'sentiment': '${emotion_result}'}, 'save_result': True}},
            ],
            'connections': [
                {'source': 'start', 'target': 'sentiment'}, {'source': 'sentiment', 'target': 'ai_report'},
                {'source': 'ai_report', 'target': 'output'},
            ]
        },
        {
            'name': '竞品情报分析',
            'description': '自动收集和分析竞争对手信息，生成竞争情报报告，支持业务决策。',
            'nodes': [
                {'id': 'start', 'name': '开始', 'node_type': 'data_input', 'position_x': 100, 'position_y': 250, 'config': {'trigger_type': 'scheduled_task', 'input_config': {'input_type': 'json', 'output_variable': 'competitor_data'}}},
                {'id': 'ai_analyze', 'name': 'AI分析', 'node_type': 'ai_generation', 'position_x': 280, 'position_y': 250, 'config': {'prompt': '分析竞品信息，提取关键情报', 'output_variable': 'intelligence'}},
                {'id': 'output', 'name': '输出报告', 'node_type': 'data_output', 'position_x': 460, 'position_y': 250, 'config': {'output_data': {'report': '${intelligence}'}, 'save_result': True}},
            ],
            'connections': [
                {'source': 'start', 'target': 'ai_analyze'}, {'source': 'ai_analyze', 'target': 'output'},
            ]
        },
        {
            'name': '营销文案生成',
            'description': '根据产品特点和目标受众，自动生成多渠道营销文案。',
            'nodes': [
                {'id': 'start', 'name': '开始', 'node_type': 'data_input', 'position_x': 100, 'position_y': 250, 'config': {'trigger_type': 'manual', 'input_config': {'input_type': 'json', 'output_variable': 'marketing_request'}}},
                {'id': 'ai_copy', 'name': 'AI生成文案', 'node_type': 'ai_generation', 'position_x': 280, 'position_y': 250, 'config': {'prompt': '生成营销文案', 'output_variable': 'copy'}},
                {'id': 'variations', 'name': '生成变体', 'node_type': 'ai_generation', 'position_x': 460, 'position_y': 250, 'config': {'prompt': '基于主文案生成3个变体版本', 'output_variable': 'variations'}},
                {'id': 'output', 'name': '输出结果', 'node_type': 'data_output', 'position_x': 640, 'position_y': 250, 'config': {'output_data': {'main_copy': '${copy}', 'variations': '${variations}'}, 'save_result': True}},
            ],
            'connections': [
                {'source': 'start', 'target': 'ai_copy'}, {'source': 'ai_copy', 'target': 'variations'},
                {'source': 'variations', 'target': 'output'},
            ]
        },
        {
            'name': '智能知识搜索',
            'description': '基于向量检索的智能知识库搜索，支持语义理解和精准匹配。',
            'nodes': [
                {'id': 'start', 'name': '开始', 'node_type': 'data_input', 'position_x': 100, 'position_y': 250, 'config': {'trigger_type': 'webhook', 'input_config': {'input_type': 'json', 'output_variable': 'search_query'}}},
                {'id': 'retrieve', 'name': '知识检索', 'node_type': 'knowledge_retrieval', 'position_x': 280, 'position_y': 250, 'config': {'query_variable': 'search_query.text', 'top_k': 10, 'output_variable': 'search_results'}},
                {'id': 'output', 'name': '输出结果', 'node_type': 'data_output', 'position_x': 460, 'position_y': 250, 'config': {'output_data': '${search_results}', 'save_result': True}},
            ],
            'connections': [
                {'source': 'start', 'target': 'retrieve'}, {'source': 'retrieve', 'target': 'output'},
            ]
        },
        {
            'name': '语音内容处理',
            'description': '自动转录语音内容，生成摘要和关键信息提取，支持多语言识别。',
            'nodes': [
                {'id': 'start', 'name': '开始', 'node_type': 'data_input', 'position_x': 100, 'position_y': 250, 'config': {'trigger_type': 'manual', 'input_config': {'input_type': 'file', 'output_variable': 'audio'}}},
                {'id': 'transcribe', 'name': '语音转文字', 'node_type': 'audio_processing', 'position_x': 280, 'position_y': 150, 'config': {'operation': 'stt', 'audio_variable': 'audio', 'output_variable': 'transcript'}},
                {'id': 'summarize', 'name': '生成摘要', 'node_type': 'ai_generation', 'position_x': 280, 'position_y': 350, 'config': {'prompt': '为语音内容生成简洁摘要', 'output_variable': 'summary'}},
                {'id': 'output', 'name': '输出结果', 'node_type': 'data_output', 'position_x': 460, 'position_y': 250, 'config': {'output_data': {'transcript': '${transcript}', 'summary': '${summary}'}, 'save_result': True}},
            ],
            'connections': [
                {'source': 'start', 'target': 'transcribe'}, {'source': 'start', 'target': 'summarize'},
                {'source': 'transcribe', 'target': 'output'}, {'source': 'summarize', 'target': 'output'},
            ]
        },
        {
            'name': '图片内容审核',
            'description': '自动识别图片内容，检测违规内容，支持批量处理和实时审核。',
            'nodes': [
                {'id': 'start', 'name': '开始', 'node_type': 'data_input', 'position_x': 100, 'position_y': 250, 'config': {'trigger_type': 'webhook', 'input_config': {'input_type': 'json', 'output_variable': 'image_data'}}},
                {'id': 'ocr', 'name': 'OCR识别', 'node_type': 'image_processing', 'position_x': 280, 'position_y': 150, 'config': {'operation': 'ocr', 'image_variable': 'image_data.url', 'output_variable': 'text_content'}},
                {'id': 'ai_analyze', 'name': 'AI内容分析', 'node_type': 'ai_generation', 'position_x': 280, 'position_y': 350, 'config': {'prompt': '分析图片内容，检查是否合规', 'output_variable': 'content_review'}},
                {'id': 'classify', 'name': '审核分类', 'node_type': 'ai_classify', 'position_x': 460, 'position_y': 250, 'config': {'categories': [{'name': '通过', 'description': '内容正常'}, {'name': '拒绝', 'description': '违规内容'}], 'output_variable': 'review_result'}},
                {'id': 'output', 'name': '输出结果', 'node_type': 'data_output', 'position_x': 640, 'position_y': 250, 'config': {'output_data': {'result': '${review_result}', 'details': '${content_review}'}, 'save_result': True}},
            ],
            'connections': [
                {'source': 'start', 'target': 'ocr'}, {'source': 'start', 'target': 'ai_analyze'},
                {'source': 'ocr', 'target': 'ai_analyze'}, {'source': 'ai_analyze', 'target': 'classify'},
                {'source': 'classify', 'target': 'output'},
            ]
        },
        {
            'name': '社交媒体监控',
            'description': '监控社交媒体上与品牌相关的讨论，分析舆情趋势，识别危机信号。',
            'nodes': [
                {'id': 'start', 'name': '开始', 'node_type': 'data_input', 'position_x': 100, 'position_y': 250, 'config': {'trigger_type': 'scheduled_task', 'input_config': {'input_type': 'json', 'output_variable': 'social_data'}}},
                {'id': 'sentiment', 'name': '情感分析', 'node_type': 'sentiment_analysis', 'position_x': 280, 'position_y': 150, 'config': {'analysis_type': 'emotion', 'output_variable': 'sentiment'}},
                {'id': 'alert', 'name': '危机警报', 'node_type': 'notification', 'position_x': 460, 'position_y': 100, 'config': {'channel': 'sms', 'title': '舆情危机预警', 'message': '检测到负面舆情！'}},
                {'id': 'output', 'name': '输出报告', 'node_type': 'data_output', 'position_x': 460, 'position_y': 250, 'config': {'output_data': {'sentiment': '${sentiment}'}, 'save_result': True}},
            ],
            'connections': [
                {'source': 'start', 'target': 'sentiment'},
                {'source': 'sentiment', 'target': 'alert', 'config': {'condition': 'contains "negative"'}},
                {'source': 'sentiment', 'target': 'output'},
            ]
        },
        {
            'name': '员工入职引导',
            'description': '自动化新员工入职流程，包括资料收集、账号开通和欢迎通知。',
            'nodes': [
                {'id': 'start', 'name': '开始', 'node_type': 'data_input', 'position_x': 100, 'position_y': 250, 'config': {'trigger_type': 'webhook', 'input_config': {'input_type': 'json', 'output_variable': 'employee_info'}}},
                {'id': 'welcome', 'name': '发送欢迎', 'node_type': 'notification', 'position_x': 280, 'position_y': 100, 'config': {'channel': 'email', 'title': '欢迎加入', 'message': '欢迎新员工！'}},
                {'id': 'create_account', 'name': '创建账号', 'node_type': 'http_request', 'position_x': 280, 'position_y': 250, 'config': {'url': 'https://api.example.com/users', 'method': 'POST', 'output_variable': 'account'}},
                {'id': 'notify_mentor', 'name': '通知导师', 'node_type': 'notification', 'position_x': 460, 'position_y': 250, 'config': {'channel': 'email', 'title': '导师分配', 'message': '您已被选为导师'}},
                {'id': 'output', 'name': '完成通知', 'node_type': 'data_output', 'position_x': 640, 'position_y': 250, 'config': {'output_data': {'status': 'completed'}, 'save_result': True}},
            ],
            'connections': [
                {'source': 'start', 'target': 'welcome'}, {'source': 'start', 'target': 'create_account'},
                {'source': 'create_account', 'target': 'notify_mentor'}, {'source': 'notify_mentor', 'target': 'output'},
            ]
        },
        {
            'name': '财务报告分析',
            'description': '自动处理财务数据，生成可视化报告，分析财务指标和趋势。',
            'nodes': [
                {'id': 'start', 'name': '开始', 'node_type': 'data_input', 'position_x': 100, 'position_y': 250, 'config': {'trigger_type': 'scheduled_task', 'input_config': {'input_type': 'json', 'output_variable': 'financial_data'}}},
                {'id': 'ai_analysis', 'name': 'AI财务分析', 'node_type': 'ai_generation', 'position_x': 280, 'position_y': 150, 'config': {'prompt': '分析财务数据，关注收入趋势和成本结构', 'output_variable': 'analysis'}},
                {'id': 'forecast', 'name': '财务预测', 'node_type': 'ai_generation', 'position_x': 280, 'position_y': 350, 'config': {'prompt': '基于历史数据进行财务预测', 'output_variable': 'forecast'}},
                {'id': 'output', 'name': '输出报告', 'node_type': 'data_output', 'position_x': 460, 'position_y': 250, 'config': {'output_data': {'analysis': '${analysis}', 'forecast': '${forecast}'}, 'save_result': True}},
            ],
            'connections': [
                {'source': 'start', 'target': 'ai_analysis'}, {'source': 'start', 'target': 'forecast'},
                {'source': 'ai_analysis', 'target': 'output'}, {'source': 'forecast', 'target': 'output'},
            ]
        },
        {
            'name': '简历智能筛选',
            'description': '自动解析简历内容，对比岗位需求进行智能评分和筛选。',
            'nodes': [
                {'id': 'start', 'name': '开始', 'node_type': 'data_input', 'position_x': 100, 'position_y': 250, 'config': {'trigger_type': 'webhook', 'input_config': {'input_type': 'json', 'output_variable': 'application_data'}}},
                {'id': 'extract', 'name': '简历解析', 'node_type': 'document_extractor', 'position_x': 280, 'position_y': 250, 'config': {'file_type': 'pdf', 'extraction_method': 'text', 'output_variable': 'resume_content'}},
                {'id': 'match', 'name': '智能匹配', 'node_type': 'ai_generation', 'position_x': 460, 'position_y': 150, 'config': {'prompt': '对比简历和岗位要求，计算匹配度', 'output_variable': 'match_result'}},
                {'id': 'score', 'name': '综合评分', 'node_type': 'ai_classify', 'position_x': 460, 'position_y': 350, 'config': {'categories': [{'name': '强烈推荐', 'description': '匹配度90%以上'}, {'name': '推荐', 'description': '匹配度70%-90%'}, {'name': '一般', 'description': '匹配度50%-70%'}], 'output_variable': 'recommendation'}},
                {'id': 'output', 'name': '输出结果', 'node_type': 'data_output', 'position_x': 640, 'position_y': 250, 'config': {'output_data': {'resume': '${resume_content}', 'recommendation': '${recommendation}'}, 'save_result': True}},
            ],
            'connections': [
                {'source': 'start', 'target': 'extract'}, {'source': 'extract', 'target': 'match'},
                {'source': 'extract', 'target': 'score'}, {'source': 'match', 'target': 'output'},
                {'source': 'score', 'target': 'output'},
            ]
        },
        {
            'name': '订单自动分类',
            'description': '自动识别和分类订单类型，路由到相应处理流程。',
            'nodes': [
                {'id': 'start', 'name': '开始', 'node_type': 'data_input', 'position_x': 100, 'position_y': 250, 'config': {'trigger_type': 'webhook', 'input_config': {'input_type': 'json', 'output_variable': 'order_data'}}},
                {'id': 'classify', 'name': '订单分类', 'node_type': 'ai_classify', 'position_x': 280, 'position_y': 250, 'config': {'categories': [{'name': '标准订单', 'description': '常规购买'}, {'name': '预售订单', 'description': '预售商品'}, {'name': '定制订单', 'description': '需要定制'}], 'output_variable': 'order_type'}},
                {'id': 'standard', 'name': '标准处理', 'node_type': 'notification', 'position_x': 460, 'position_y': 50, 'config': {'channel': 'system', 'title': '标准订单', 'message': '路由到标准处理流程'}},
                {'id': 'presale', 'name': '预售处理', 'node_type': 'notification', 'position_x': 460, 'position_y': 150, 'config': {'channel': 'system', 'title': '预售订单', 'message': '路由到预售处理流程'}},
                {'id': 'custom', 'name': '定制处理', 'node_type': 'notification', 'position_x': 460, 'position_y': 250, 'config': {'channel': 'system', 'title': '定制订单', 'message': '路由到定制生产流程'}},
                {'id': 'output', 'name': '输出结果', 'node_type': 'data_output', 'position_x': 640, 'position_y': 250, 'config': {'output_data': {'order_type': '${order_type}'}, 'save_result': True}},
            ],
            'connections': [
                {'source': 'start', 'target': 'classify'},
                {'source': 'classify', 'target': 'standard', 'config': {'condition': 'contains "标准"'}},
                {'source': 'classify', 'target': 'presale', 'config': {'condition': 'contains "预售"'}},
                {'source': 'classify', 'target': 'custom', 'config': {'condition': 'contains "定制"'}},
                {'source': 'standard', 'target': 'output'}, {'source': 'presale', 'target': 'output'},
                {'source': 'custom', 'target': 'output'},
            ]
        },
        {
            'name': '智能定价助手',
            'description': '基于市场数据、竞品分析和历史销售数据，提供智能定价建议。',
            'nodes': [
                {'id': 'start', 'name': '开始', 'node_type': 'data_input', 'position_x': 100, 'position_y': 250, 'config': {'trigger_type': 'manual', 'input_config': {'input_type': 'json', 'output_variable': 'pricing_request'}}},
                {'id': 'market', 'name': '市场分析', 'node_type': 'ai_generation', 'position_x': 280, 'position_y': 100, 'config': {'prompt': '分析市场行情', 'output_variable': 'market_analysis'}},
                {'id': 'competitor', 'name': '竞品分析', 'node_type': 'ai_generation', 'position_x': 280, 'position_y': 200, 'config': {'prompt': '分析竞品价格', 'output_variable': 'competitor_analysis'}},
                {'id': 'recommend', 'name': '定价建议', 'node_type': 'ai_generation', 'position_x': 280, 'position_y': 300, 'config': {'prompt': '综合分析给出定价建议', 'output_variable': 'pricing_recommendation'}},
                {'id': 'output', 'name': '输出结果', 'node_type': 'data_output', 'position_x': 460, 'position_y': 250, 'config': {'output_data': {'recommendation': '${pricing_recommendation}'}, 'save_result': True}},
            ],
            'connections': [
                {'source': 'start', 'target': 'market'}, {'source': 'start', 'target': 'competitor'},
                {'source': 'start', 'target': 'recommend'}, {'source': 'recommend', 'target': 'output'},
            ]
        },
        {
            'name': '客户投诉处理',
            'description': '自动接收和分类客户投诉，智能生成回复方案，跟踪处理进度。',
            'nodes': [
                {'id': 'start', 'name': '开始', 'node_type': 'data_input', 'position_x': 100, 'position_y': 250, 'config': {'trigger_type': 'webhook', 'input_config': {'input_type': 'json', 'output_variable': 'complaint'}}},
                {'id': 'sentiment', 'name': '情感分析', 'node_type': 'sentiment_analysis', 'position_x': 280, 'position_y': 150, 'config': {'analysis_type': 'emotion', 'output_variable': 'sentiment'}},
                {'id': 'classify', 'name': '投诉分类', 'node_type': 'ai_classify', 'position_x': 280, 'position_y': 350, 'config': {'categories': [{'name': '产品质量', 'description': '产品相关问题'}, {'name': '服务态度', 'description': '服务相关问题'}, {'name': '物流配送', 'description': '配送相关问题'}], 'output_variable': 'category'}},
                {'id': 'response', 'name': '生成回复', 'node_type': 'ai_generation', 'position_x': 460, 'position_y': 250, 'config': {'prompt': '为投诉生成专业回复', 'output_variable': 'response_template'}},
                {'id': 'output', 'name': '输出结果', 'node_type': 'data_output', 'position_x': 640, 'position_y': 250, 'config': {'output_data': {'category': '${category}', 'response': '${response_template}'}, 'save_result': True}},
            ],
            'connections': [
                {'source': 'start', 'target': 'sentiment'}, {'source': 'start', 'target': 'classify'},
                {'source': 'sentiment', 'target': 'response'}, {'source': 'classify', 'target': 'response'},
                {'source': 'response', 'target': 'output'},
            ]
        },
        {
            'name': '市场趋势预测',
            'description': '基于历史数据和外部信号，预测市场趋势变化，为业务决策提供数据支持。',
            'nodes': [
                {'id': 'start', 'name': '开始', 'node_type': 'data_input', 'position_x': 100, 'position_y': 250, 'config': {'trigger_type': 'scheduled_task', 'input_config': {'input_type': 'json', 'output_variable': 'market_data'}}},
                {'id': 'analyze', 'name': '趋势分析', 'node_type': 'ai_generation', 'position_x': 280, 'position_y': 150, 'config': {'prompt': '分析市场数据的变化趋势', 'output_variable': 'trend_analysis'}},
                {'id': 'forecast', 'name': '未来预测', 'node_type': 'ai_generation', 'position_x': 280, 'position_y': 350, 'config': {'prompt': '预测未来3个月的市场趋势', 'output_variable': 'forecast'}},
                {'id': 'output', 'name': '输出报告', 'node_type': 'data_output', 'position_x': 460, 'position_y': 250, 'config': {'output_data': {'forecast': '${forecast}'}, 'save_result': True}},
            ],
            'connections': [
                {'source': 'start', 'target': 'analyze'}, {'source': 'start', 'target': 'forecast'},
                {'source': 'analyze', 'target': 'output'}, {'source': 'forecast', 'target': 'output'},
            ]
        },
        {
            'name': '产品反馈汇总',
            'description': '收集和分析产品用户反馈，生成产品改进建议，支持产品迭代和优化决策。',
            'nodes': [
                {'id': 'start', 'name': '开始', 'node_type': 'data_input', 'position_x': 100, 'position_y': 250, 'config': {'trigger_type': 'scheduled_task', 'input_config': {'input_type': 'json', 'output_variable': 'feedback_data'}}},
                {'id': 'sentiment', 'name': '情感分析', 'node_type': 'sentiment_analysis', 'position_x': 280, 'position_y': 150, 'config': {'analysis_type': 'emotion', 'output_variable': 'sentiment_analysis'}},
                {'id': 'topic', 'name': '话题聚类', 'node_type': 'ai_generation', 'position_x': 280, 'position_y': 350, 'config': {'prompt': '将用户反馈按产品功能分类', 'output_variable': 'topic_cluster'}},
                {'id': 'recommend', 'name': '改进建议', 'node_type': 'ai_generation', 'position_x': 460, 'position_y': 250, 'config': {'prompt': '基于反馈分析给出产品改进建议', 'output_variable': 'improvement_suggestions'}},
                {'id': 'output', 'name': '输出报告', 'node_type': 'data_output', 'position_x': 640, 'position_y': 250, 'config': {'output_data': {'suggestions': '${improvement_suggestions}'}, 'save_result': True}},
            ],
            'connections': [
                {'source': 'start', 'target': 'sentiment'}, {'source': 'start', 'target': 'topic'},
                {'source': 'sentiment', 'target': 'recommend'}, {'source': 'topic', 'target': 'recommend'},
                {'source': 'recommend', 'target': 'output'},
            ]
        },
    ]

def main():
    print("=" * 60)
    print("开始创建20个企业级AI工作流...")
    print("=" * 60)
    
    workflows = get_enterprise_workflows()
    print(f"\n准备创建 {len(workflows)} 个工作流...\n")
    
    created = create_workflow(workflows)
    
    print("\n" + "=" * 60)
    print(f"✓ 成功创建 {len(created)} 个企业级AI工作流！")
    print("=" * 60)
    
    for wf in created:
        print(f"  - {wf.name}")
    
    print("\n所有工作流已设置为：")
    print("  - 状态: 已发布")
    print("  - 公开: 是")

if __name__ == '__main__':
    main()
