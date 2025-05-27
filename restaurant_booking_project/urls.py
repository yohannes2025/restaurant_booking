# restaurant_booking_project/urls.py
from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('bookings.urls')),  # Include bookings app URLs
    path('accounts/', include('django.contrib.auth.urls')),
]
# path('logout/', auth_views.LogoutView.as_view(), name='account_logout'),
# For login/logout/password reset
# path('accounts/', include([
#     path('login/', auth_views.LoginView.as_view(), name='login'),
#     path('logout/', auth_views.LogoutView.as_view(), name='account_logout'),    
# ]))
