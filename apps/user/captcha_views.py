from django.http import HttpResponse
from django.views.decorators.http import require_GET
from captcha.models import CaptchaStore
from captcha.helpers import captcha_image_url
import json


@require_GET
def captcha_image(request, key):
    try:
        captcha = CaptchaStore.objects.get(hashkey=key)
        image_url = captcha_image_url(key)
        return HttpResponse(json.dumps({
            'status': 1,
            'img_url': image_url
        }))
    except CaptchaStore.DoesNotExist:
        return HttpResponse(json.dumps({
            'status': 0,
            'error': 'Invalid captcha key'
        }), status=400)


@require_GET
def refresh_captcha(request):
    new_key = CaptchaStore.generate_key()
    return HttpResponse(json.dumps({
        'status': 1,
        'key': new_key,
        'img_url': captcha_image_url(new_key)
    }))
