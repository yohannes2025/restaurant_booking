# # bookings/models.py
# from django.db import models
# from django.contrib.auth.models import User  # For linking bookings to users


# class Table(models.Model):
#     """Represents a restaurant table."""
#     number = models.IntegerField(unique=True)
#     capacity = models.IntegerField(
#         help_text="Maximum number of guests this table can accommodate.")

#     def __str__(self):
#         return f"Table {self.number} (Capacity: {self.capacity})"


# class Booking(models.Model):
#     """Represents a table reservation."""
#     user = models.ForeignKey(
#         User, on_delete=models.CASCADE, related_name='bookings')
#     table = models.ForeignKey(
#         Table, on_delete=models.CASCADE, related_name='bookings')
#     booking_date = models.DateField()
#     booking_time = models.TimeField()
#     number_of_guests = models.IntegerField()
#     notes = models.TextField(blank=True, null=True)
#     created_at = models.DateTimeField(auto_now_add=True)

#     class Meta:
#         # Ensures that a table cannot be booked by the same user at the exact same date and time
#         unique_together = ('table', 'booking_date', 'booking_time')
#         ordering = ['booking_date', 'booking_time']

#     def __str__(self):
#         return f"Booking by {self.user.username} for Table {self.table.number} on {self.booking_date} at {self.booking_time}"


# bookings/models.py
from django.db import models
from django.contrib.auth.models import User
from datetime import date, time  # Import these if not already present


class Table(models.Model):
    number = models.IntegerField(unique=True)
    capacity = models.IntegerField(
        help_text="Maximum number of guests this table can accommodate.")

    def __str__(self):
        return f"Table {self.number} (Capacity: {self.capacity})"


class Booking(models.Model):
    BOOKING_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('cancelled', 'Cancelled'),
        ('no-show', 'No-Show'),
        ('completed', 'Completed'),  # For past bookings that were honored
    ]

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='bookings')
    table = models.ForeignKey(
        Table, on_delete=models.CASCADE, related_name='bookings')
    booking_date = models.DateField()
    booking_time = models.TimeField()
    number_of_guests = models.IntegerField()
    notes = models.TextField(blank=True, null=True)
    status = models.CharField(
        max_length=20, choices=BOOKING_STATUS_CHOICES, default='pending')  # New field
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('table', 'booking_date', 'booking_time')
        ordering = ['booking_date', 'booking_time']

    def __str__(self):
        return f"Booking by {self.user.username} for Table {self.table.number} on {self.booking_date} at {self.booking_time} ({self.status})"
