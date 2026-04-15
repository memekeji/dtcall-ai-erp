from django.http import JsonResponse
from django.views import View
from django.urls import reverse
from captcha.models import CaptchaStore


class GetNewCaptchaView(View):
    def get(self, request):
        key = CaptchaStore.generate_key()
        return JsonResponse({
            'key': key,
            'image_url': request.build_absolute_uri(reverse('captcha-image', kwargs={'key': key}))
        })
