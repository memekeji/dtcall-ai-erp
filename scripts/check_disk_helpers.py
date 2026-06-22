import os
import sys
import inspect
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dtcall.settings')

import django
django.setup()

from apps.disk import views


assert callable(views._soft_delete_folder_recursive)
assert callable(views._permanent_delete_folder_recursive)
assert not hasattr(views.FolderDeleteView, 'soft_delete_folder_recursive')
assert not hasattr(views.FolderDeleteView, 'permanent_delete_folder_recursive')
assert not hasattr(views.RecycleBinClearView, 'permanent_delete_folder_recursive')

folder_delete_source = inspect.getsource(views.FolderDeleteView.post)
assert '_soft_delete_folder_recursive(folder)' in folder_delete_source
assert '_permanent_delete_folder_recursive(folder)' in folder_delete_source

print('disk helper checks passed')
