import os
import sys
from pathlib import Path
from wsgiref.simple_server import make_server
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
os.chdir(str(BASE_DIR))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dtcall.settings')
from dtcall.wsgi import application
httpd = make_server('127.0.0.1', 8003, application)
print('serving on 127.0.0.1:8003', flush=True)
httpd.serve_forever()
