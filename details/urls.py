from django.urls import path
from .views import details_page

urlpatterns = [
    path('', details_page, name='details_page'),
]
