# restaurant_booking_project/urls.py
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('bookings.urls')),  # Include bookings app URLs
    # For login/logout/password reset
    path('accounts/', include('django.contrib.auth.urls')),
]
