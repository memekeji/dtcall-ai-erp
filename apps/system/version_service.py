# -*- coding: utf-8 -*-
import json, logging, os, subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional
from django.conf import settings

logger = logging.getLogger('django')
BASE_DIR = Path(settings.BASE_DIR)

def get_current_version():
    p = BASE_DIR / 'VERSION'
    return p.read_text(encoding='utf-8').strip() if p.exists() else '0.0.0'

def get_current_commit():
    try:
        r = subprocess.run(['git','rev-parse','--short','HEAD'], cwd=str(BASE_DIR),
            capture_output=True, text=True, timeout=10)
        return r.stdout.strip() if r.returncode == 0 else 'unknown'
    except: return 'unknown'

def get_current_branch():
    try:
        r = subprocess.run(['git','rev-parse','--abbrev-ref','HEAD'], cwd=str(BASE_DIR),
            capture_output=True, text=True, timeout=10)
        return r.stdout.strip() if r.returncode == 0 else 'unknown'
    except: return 'unknown'

def get_latest_tag():
    try:
        r = subprocess.run(['git','tag','--sort=-version:refname'], cwd=str(BASE_DIR),
            capture_output=True, text=True, timeout=10)
        if r.returncode != 0: return None
        tags = [t for t in r.stdout.strip().split('\n') if t and t[0].isdigit()]
        return tags[0] if tags else None
    except: return None

def check_for_updates():
    current = get_current_version()
    commit = get_current_commit()
    try:
        subprocess.run(['git','fetch','--tags','--quiet'], cwd=str(BASE_DIR),
            capture_output=True, text=True, timeout=30)
    except: pass
    latest = get_latest_tag()
    result = {'current_version':current,'current_commit':commit,'latest_version':latest,
        'update_available':False,'changelog':[],'checked_at':datetime.now().isoformat()}
    if latest and latest != current:
        result['update_available'] = True
        try:
            r = subprocess.run(['git','log','--oneline','--no-decorate',f'HEAD..{latest}'],
                cwd=str(BASE_DIR), capture_output=True, text=True, timeout=10)
            if r.returncode == 0 and r.stdout.strip():
                result['changelog'] = r.stdout.strip().split('\n')[:50]
        except: pass
    return result

def backup_database():
    eng = settings.DATABASES.get('default',{}).get('ENGINE','')
    d = BASE_DIR / 'backups' / 'pre_update'; d.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S'); ver = get_current_version()
    if 'postgresql' in eng or 'postgis' in eng:
        ds = settings.DATABASES['default']
        fp = d / f'pre_update_backup_{ver}_{ts}.dump'
        env = os.environ.copy(); env['PGPASSWORD'] = ds.get('PASSWORD','')
        try:
            r = subprocess.run(['pg_dump','-h',ds.get('HOST','localhost'),'-p',str(ds.get('PORT',5432)),
                '-U',ds.get('USER','postgres'),'-d',ds.get('NAME','dtcall'),'-F','c','-f',str(fp)],
                capture_output=True, text=True, timeout=300, env=env)
            if r.returncode == 0:
                logger.info('Backup created: %s (%s bytes)', fp, fp.stat().st_size)
                return {'success':True,'file':str(fp),'size_bytes':fp.stat().st_size}
            return {'success':False,'error':r.stderr.strip()}
        except FileNotFoundError: return {'success':False,'error':'pg_dump not found'}
        except Exception as ex: return {'success':False,'error':str(ex)}
    elif 'sqlite' in eng:
        import shutil
        dbp = Path(ds.get('NAME', BASE_DIR/'db.sqlite3'))
        if not dbp.is_absolute(): dbp = BASE_DIR / dbp
        fp = d / f'pre_update_backup_{ver}_{ts}.sqlite3'
        if not dbp.exists(): return {'success':False,'error':f'DB not found: {dbp}'}
        shutil.copy2(str(dbp), str(fp))
        return {'success':True,'file':str(fp),'size_bytes':fp.stat().st_size}
    return {'success':False,'error':f'Unsupported engine: {eng}'}

def perform_update(target_version=None):
    target = target_version or get_latest_tag()
    if not target: return {'success':False,'error':'No target version available'}
    cur_commit = get_current_commit(); cur_version = get_current_version()
    rb = {'previous_commit':cur_commit,'previous_version':cur_version,'target_version':target,'timestamp':datetime.now().isoformat()}
    (BASE_DIR/'.rollback_state').write_text(json.dumps(rb, indent=2))
    try:
        r = subprocess.run(['git','fetch','--tags','--quiet'], cwd=str(BASE_DIR),
            capture_output=True, text=True, timeout=30)
        if r.returncode != 0: return {'success':False,'error':f'Fetch failed: {r.stderr.strip()}'}
    except Exception as ex: return {'success':False,'error':str(ex)}
    try:
        r = subprocess.run(['git','checkout',target], cwd=str(BASE_DIR),
            capture_output=True, text=True, timeout=30)
        if r.returncode != 0: return {'success':False,'error':f'Checkout failed: {r.stderr.strip()}'}
    except Exception as ex: return {'success':False,'error':str(ex)}
    try: (BASE_DIR/'VERSION').write_text(target, encoding='utf-8')
    except: pass
    try:
        from django.core.management import call_command
        call_command('migrate', interactive=False, verbosity=0)
    except Exception as ex:
        logger.error('Migration failed: %s', ex)
        return {'success':False,'error':f'Migration failed: {ex}','stage':'migrate'}
    try: call_command('collectstatic', interactive=False, verbosity=0)
    except: pass
    new_commit = get_current_commit()
    logger.info('Update to %s completed', target)
    return {'success':True,'new_version':target,'previous_version':cur_version,
        'previous_commit':cur_commit,'new_commit':new_commit}

def get_rollback_info():
    p = BASE_DIR / '.rollback_state'
    return json.loads(p.read_text(encoding='utf-8')) if p.exists() else None

def perform_rollback():
    rb = get_rollback_info()
    if not rb: return {'success':False,'error':'No rollback state found'}
    try:
        r = subprocess.run(['git','checkout',rb['previous_commit']], cwd=str(BASE_DIR),
            capture_output=True, text=True, timeout=30)
        if r.returncode != 0: return {'success':False,'error':f'Checkout failed: {r.stderr.strip()}'}
    except Exception as ex: return {'success':False,'error':str(ex)}
    try:
        from django.core.management import call_command
        call_command('migrate', interactive=False, verbosity=0)
    except Exception as ex:
        return {'success':False,'error':f'Rollback migration failed: {ex}','stage':'migrate'}
    (BASE_DIR/'VERSION').write_text(rb['previous_version'], encoding='utf-8')
    (BASE_DIR/'.rollback_state').unlink(missing_ok=True)
    logger.info('Rollback to %s completed', rb['previous_version'])
    return {'success':True,'restored_version':rb['previous_version'],'restored_commit':rb['previous_commit']}

def get_system_health():
    from django.db import connections
    db_ok = False
    try: connections['default'].cursor(); db_ok = True
    except: pass
    return {'status':'healthy' if db_ok else 'degraded','database':'connected' if db_ok else 'disconnected',
        'version':get_current_version(),'commit':get_current_commit(),'branch':get_current_branch(),
        'checked_at':datetime.now().isoformat()}
