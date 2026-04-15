import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dtcall.settings')
django.setup()

from django.apps import apps

for model in apps.get_models():
    try:
        # Check if the __str__ method returns self.name but there is no name field
        if not hasattr(model, 'name'):
            # try to instantiate and call str()
            try:
                obj = model()
                str(obj)
            except AttributeError as e:
                if "' name'" in str(e) or "'name'" in str(e) or "has no attribute 'name'" in str(e):
                    print(f"Model {model.__name__} in {model._meta.app_label} has a buggy __str__ method (no name attribute).")
    except Exception as e:
        pass
