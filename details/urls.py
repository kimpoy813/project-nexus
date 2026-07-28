from django.urls import path
from .views import details_page, reports_page, achievements_page

urlpatterns = [
    path('', details_page, name='details_page'),
    path('reports/', reports_page, name='reports_page'),
    path('achievements/', achievements_page, name='achievements_page'),
]
