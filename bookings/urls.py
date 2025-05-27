# bookings/urls.py
from django.urls import path
from . import views
from .views import staff_table_edit, register

urlpatterns = [
    path('', views.home_view, name='home'),
    path('book/', views.make_booking, name='make_booking'),
    path('my-bookings/', views.my_bookings, name='my_bookings'),
    path('cancel-booking/<int:booking_id>/',
         views.cancel_booking, name='cancel_booking'),
    path('check-availability/', views.check_availability,
         name='check_availability'),
    path('register/', register, name='register'),  # Add this line
    # Staff Dashboard URLs
    path('staff/', views.staff_dashboard, name='staff_dashboard'),
    path('staff/bookings/', views.staff_booking_list, name='staff_booking_list'),
    path('staff/bookings/<int:booking_id>/',
         views.staff_booking_detail, name='staff_booking_detail'),
    path('staff/tables/', views.staff_table_list, name='staff_table_list'),
    path('staff/tables/<int:table_id>/edit/',
         staff_table_edit, name='staff_table_edit'),
    path('staff/tables/<int:table_id>/delete/',
         views.staff_table_delete, name='staff_table_delete'),
]
