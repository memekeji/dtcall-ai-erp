from django.urls import path
from .views import DailyQuoteView

app_name = 'common'

urlpatterns = [
    path('daily-quote/', DailyQuoteView.as_view(), name='daily_quote'),
]
