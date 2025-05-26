# bookings/admin.py
from django.contrib import admin
from .models import Table, Booking


@admin.register(Table)
class TableAdmin(admin.ModelAdmin):
    list_display = ('number', 'capacity')
    search_fields = ('number',)


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ('user', 'table', 'booking_date',
                    'booking_time', 'number_of_guests', 'created_at')
    list_filter = ('booking_date', 'booking_time', 'table__capacity')
    search_fields = ('user__username', 'table__number')
    date_hierarchy = 'booking_date'
