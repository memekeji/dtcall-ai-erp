from django.urls import path

from . import ai_views, views


app_name = 'supply_chain'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('source-sync/', views.source_sync, name='source_sync'),
    path('inventory-analysis/', views.inventory_analysis, name='inventory_analysis'),

    path('forecast/', views.forecast_list, name='forecast_list'),
    path('forecast/create/', views.forecast_create, name='forecast_create'),
    path('forecast/trend/', views.forecast_trend, name='forecast_trend'),

    path('forecast/<int:pk>/run/', views.forecast_run, name='forecast_run'),
    path('forecast/review/<int:pk>/', views.forecast_review, name='forecast_review'),
    path('forecast/<int:pk>/qa/', views.forecast_qa, name='forecast_qa'),

    path('outsource/', views.outsource_list, name='outsource_list'),
    path('outsource/create/', views.outsource_create, name='outsource_create'),
    path('outsource/generate-from-plan/', views.outsource_generate_from_plan, name='outsource_generate_from_plan'),

    path('outsource/<int:pk>/check/', views.outsource_check, name='outsource_check'),
    path('outsource/<int:pk>/status/', views.outsource_status_update, name='outsource_status_update'),

    path('pr-review/', views.pr_review_list, name='pr_review_list'),
    path('pr-review/create/', views.pr_review_create, name='pr_review_create'),
    path('pr-review/<int:pk>/evaluate/', views.pr_review_evaluate, name='pr_review_evaluate'),
    path('pr-review/<int:pk>/approve/', views.pr_review_approve, name='pr_review_approve'),
    path('pr-review/batch-approve/', views.pr_review_batch_approve, name='pr_review_batch_approve'),

    path('price-review/', views.price_review_list, name='price_review_list'),
    path('price-review/create/', views.price_review_create, name='price_review_create'),
    path('price-review/report/', views.price_review_report, name='price_review_report'),

    path('price-review/<int:pk>/analyze/', views.price_review_analyze, name='price_review_analyze'),
    path('price-review/<int:pk>/parse-document/', views.price_review_parse_document, name='price_review_parse_document'),

    path('sample/', views.sample_list, name='sample_list'),
    path('sample/create/', views.sample_create, name='sample_create'),
    path('sample/statistics/', views.sample_statistics, name='sample_statistics'),

    path('sample/<int:pk>/receive/', views.sample_receive, name='sample_receive'),
    path('sample/<int:pk>/pickup/', views.sample_pickup, name='sample_pickup'),
    path('sample/<int:pk>/remind/', views.sample_remind, name='sample_remind'),

    path('ai/forecast/<int:pk>/summary/', ai_views.forecast_ai_summary, name='forecast_ai_summary'),
    path('ai/pr-review/<int:pk>/summary/', ai_views.pr_review_ai_summary, name='pr_review_ai_summary'),
    path('ai/price-review/<int:pk>/summary/', ai_views.price_review_ai_summary, name='price_review_ai_summary'),
]
