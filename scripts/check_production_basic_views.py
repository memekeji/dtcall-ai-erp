import os
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dtcall.settings')

import django
django.setup()

from django.test import RequestFactory
from django.urls import resolve, reverse

from apps.production import views


route_expectations = {
    'production:procedure_add': views.procedure_add,
    'production:procedure_edit': views.procedure_edit,
    'production:procedure_delete': views.procedure_delete,
    'production:procedureset_add': views.procedureset_add,
    'production:bom_add': views.bom_add,
    'production:equipment_edit': views.equipment_edit,
    'production:sop_delete': views.sop_delete,
    'production:production_plan_add': views.production_plan_add,
    'production:production_task_edit': views.production_task_edit,
    'production:quality_check_add': views.quality_check_add,
    'production:process_route_delete': views.process_route_delete,
}

for route_name, expected_func in route_expectations.items():
    kwargs = {'pk': 1} if any(part in route_name for part in ['_edit', '_delete']) else {}
    path = reverse(route_name, kwargs=kwargs)
    assert resolve(path).func is expected_func, f'{route_name} should resolve to {expected_func.__name__}'


class DummyForm:
    saved = False

    def __init__(self, data=None, instance=None):
        self.data = data
        self.instance = instance

    def is_valid(self):
        return True

    def save(self):
        DummyForm.saved = True


class MessageRecorder:
    def __init__(self):
        self.items = []

    def success(self, request, message):
        self.items.append(message)


factory = RequestFactory()
captured = {}
original_render = views.render
original_redirect = views.redirect
original_messages = views.messages


def fake_render(request, template_name, context):
    captured['template_name'] = template_name
    captured['context'] = context
    return SimpleNamespace(template_name=template_name, context=context)


def fake_redirect(route_name):
    captured['redirect'] = route_name
    return SimpleNamespace(route_name=route_name)


try:
    views.render = fake_render
    views.redirect = fake_redirect
    recorder = MessageRecorder()
    views.messages = recorder

    get_response = views._render_model_form(
        factory.get('/dummy/'),
        DummyForm,
        'production/dummy/form.html',
        'production:procedure_list',
        '测试对象'
    )
    assert get_response.template_name == 'production/dummy/form.html'
    assert captured['context']['action'] == '添加'
    assert isinstance(captured['context']['form'], DummyForm)

    post_response = views._render_model_form(
        factory.post('/dummy/', data={'name': 'demo'}),
        DummyForm,
        'production/dummy/form.html',
        'production:procedure_list',
        '测试对象'
    )
    assert post_response.route_name == 'production:procedure_list'
    assert DummyForm.saved
    assert recorder.items[-1] == '测试对象添加成功'
finally:
    views.render = original_render
    views.redirect = original_redirect
    views.messages = original_messages

print('production basic view checks passed')
