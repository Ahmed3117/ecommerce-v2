from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from . import views
app_name="accounts"

urlpatterns = [
    path('signup/', views.signup, name='signup'),
    path('signin/', views.signin, name='signin'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('password-reset/', views.request_password_reset, name='password_reset'),
    path('password-reset/confirm/', views.reset_password_confirm, name='password_reset_confirm'),
    path('update-user-data/', views.UpdateUserData.as_view(), name='update-user-data'),
    path('get-user-data/', views.GetUserData.as_view(), name='get-user-data'),
    path('profile/', views.UserProfileView.as_view(), name='user-profile'),
    path('change-password/', views.change_password, name='change_password'),
    # Addresses
    path('addresses/', views.UserAddressListCreateView.as_view(), name='user-address-list-create'),
    path('addresses/<int:pk>/', views.UserAddressRetrieveUpdateDestroyView.as_view(), name='user-address-detail'),
    #-----------------Admin--------------------------#
    path('dashboard/create-admin-user/', views.create_admin_user, name='create-admin-user'),
    path('dashboard/users/create/', views.UserCreateAPIView.as_view(), name='user-create'),
    path('dashboard/users/update/<str:username>/', views.UserUpdateAPIView.as_view(), name='user-update'),
    path('dashboard/users/delete/<int:pk>/', views.UserDeleteAPIView.as_view(), name='user-delete'),
    # User profile image 
    path('dashboard/profile-images/', views.UserProfileImageListCreateView.as_view(), name='profile-image-list'),
    path('dashboard/profile-images/<int:pk>/', views.UserProfileImageRetrieveUpdateDestroyView.as_view(), name='profile-image-detail'),
    # user analysis
    path('dashboard/users/', views.AdminUserListView.as_view(), name='admin-user-list'),
    path('dashboard/users/<int:pk>/', views.AdminUserDetailView.as_view(), name='admin-user-detail'),
]


