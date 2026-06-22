from django.http import HttpResponse
from django.middleware.csrf import get_token
from django.shortcuts import redirect
from django.template.loader import get_template
from django.views.decorators.http import require_http_methods

from apps.system.database_setup import (
    apply_database_config,
    build_database_config,
    current_form_values,
    get_database_state,
    run_base_migrations,
    save_database_environment,
    test_database_config,
)


@require_http_methods(['GET', 'POST'])
def database_setup_view(request):
    state = get_database_state(force=True)
    if state.is_locked:
        return redirect('/')

    context = {
        'csrf_token': get_token(request),
        'state': state,
        'values': current_form_values(),
        'errors': [],
        'success': False,
    }

    if request.method == 'POST':
        values = _posted_values(request)
        context['values'] = values
        try:
            config = build_database_config(values)
            test_database_config(config)
            save_database_environment(values)
            apply_database_config(config)
            migrated_state = run_base_migrations()
            context['state'] = migrated_state
            context['success'] = migrated_state.is_locked
            if not migrated_state.is_locked:
                context['errors'].append('迁移已执行，但未检测到数据表，请检查迁移输出。')
        except Exception as exc:
            context['errors'].append(str(exc))

    template = get_template('setup/database.html')
    return HttpResponse(template.render(context))


def _posted_values(request):
    engine = request.POST.get('DATABASE_ENGINE', 'postgresql').strip()
    is_sqlite = engine.lower() in ('sqlite', 'sqlite3')
    default_name = 'db.sqlite3' if is_sqlite else 'dtcall'
    values = {
        'DATABASE_URL': request.POST.get('DATABASE_URL', '').strip(),
        'DATABASE_ENGINE': engine,
        'DATABASE_HOST': request.POST.get('DATABASE_HOST', '').strip(),
        'DATABASE_PORT': request.POST.get('DATABASE_PORT', '').strip(),
        'DATABASE_NAME': (
            request.POST.get('DATABASE_NAME', '').strip() or default_name
        ),
        'DATABASE_USER': request.POST.get('DATABASE_USER', '').strip(),
        'DATABASE_PASSWORD': request.POST.get('DATABASE_PASSWORD', '').strip(),
        'DATABASE_CONN_MAX_AGE': request.POST.get(
            'DATABASE_CONN_MAX_AGE', '1800').strip(),
        'DATABASE_CONN_HEALTH_CHECKS': request.POST.get(
            'DATABASE_CONN_HEALTH_CHECKS', 'True').strip(),
        'DATABASE_CONNECT_TIMEOUT': request.POST.get(
            'DATABASE_CONNECT_TIMEOUT', '10').strip(),
        'MYSQL_CHARSET': request.POST.get('MYSQL_CHARSET', 'utf8mb4').strip(),
        'MYSQL_INIT_COMMAND': request.POST.get('MYSQL_INIT_COMMAND', '').strip(),
    }
    if is_sqlite:
        values.update({
            'DATABASE_URL': '',
            'DATABASE_HOST': '',
            'DATABASE_PORT': '',
            'DATABASE_USER': '',
            'DATABASE_PASSWORD': '',
            'DATABASE_CONN_MAX_AGE': '0',
            'DATABASE_CONN_HEALTH_CHECKS': 'False',
            'DATABASE_CONNECT_TIMEOUT': '',
            'MYSQL_CHARSET': '',
            'MYSQL_INIT_COMMAND': '',
        })
    return values
