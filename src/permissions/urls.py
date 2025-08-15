from django.urls import path
from . import views

app_name = 'permissions'

urlpatterns = [
    # Frontend Pages URLs
    path('frontend-pages/', views.FrontEndPageListView.as_view(), name='frontend-pages-list'),
    path('assign-frontend-pages/', views.assign_frontend_pages, name='assign-frontend-pages'),
    path('user/<int:user_id>/allowed-frontend-pages/', views.get_user_frontend_pages, name='user-frontend-pages'),
]
