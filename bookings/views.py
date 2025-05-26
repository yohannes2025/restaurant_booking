# bookings/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.utils import timezone
from datetime import datetime, timedelta

from .models import Booking, Table
from .forms import BookingForm


def home_view(request):
    """Render the homepage."""
    return render(request, 'bookings/home.html')


@login_required
def make_booking(request):
    """Handle the booking creation form."""
    if request.method == 'POST':
        form = BookingForm(request.POST)
        if form.is_valid():
            booking_date = form.cleaned_data['booking_date']
            booking_time = form.cleaned_data['booking_time']
            number_of_guests = form.cleaned_data['number_of_guests']

            # Combine date and time, then make it timezone-aware
            booking_datetime = datetime.combine(booking_date, booking_time)
            booking_datetime = timezone.make_aware(booking_datetime)

            # Check if the booking is in the past
            if booking_datetime < timezone.now():
                messages.error(
                    request, "You cannot make a booking in the past.")
                return render(request, 'bookings/make_booking.html', {'form': form})

            # Find available tables
            booked_tables_ids = Booking.objects.filter(
                booking_date=booking_date,
                booking_time=booking_time
            ).values_list('table__id', flat=True)

            available_tables = Table.objects.filter(
                capacity__gte=number_of_guests
            ).exclude(id__in=booked_tables_ids).order_by('capacity')

            if available_tables.exists():
                selected_table = available_tables.first()
                try:
                    with transaction.atomic():
                        booking = form.save(commit=False)
                        booking.user = request.user
                        booking.table = selected_table
                        booking.save()
                        messages.success(
                            request, f"Your booking for Table {selected_table.number} has been confirmed!")
                        return redirect('my_bookings')
                except Exception as e:
                    messages.error(
                        request, f"An error occurred during booking: {e}")
            else:
                messages.warning(
                    request, "No tables available for your requested date, time, and number of guests.")
        else:
            messages.error(request, "Please correct the errors in the form.")
    else:
        form = BookingForm()
    return render(request, 'bookings/make_booking.html', {'form': form})


@login_required
def my_bookings(request):
    """Display a list of the current user's bookings."""
    upcoming_bookings = Booking.objects.filter(
        user=request.user,
        booking_date__gte=timezone.now().date()
    ).order_by('booking_date', 'booking_time')

    past_bookings = Booking.objects.filter(
        user=request.user,
        booking_date__lt=timezone.now().date()
    ).order_by('-booking_date', '-booking_time')

    context = {
        'upcoming_bookings': upcoming_bookings,
        'past_bookings': past_bookings,
    }
    return render(request, 'bookings/my_bookings.html', context)


@login_required
def cancel_booking(request, booking_id):
    """Allow a user to cancel their booking."""
    booking = get_object_or_404(Booking, id=booking_id, user=request.user)

    # Combine date and time, then make it timezone-aware
    booking_datetime = datetime.combine(
        booking.booking_date, booking.booking_time)
    booking_datetime = timezone.make_aware(booking_datetime)

    if booking_datetime < timezone.now() + timedelta(hours=2):
        messages.error(
            request, "Bookings cannot be cancelled within 2 hours of the reservation time.")
    else:
        booking.delete()
        messages.success(
            request, "Your booking has been successfully cancelled.")

    return redirect('my_bookings')
