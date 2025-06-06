# bookings/views.py
# Standard library
import os
from bookings.models import Booking, Table
from django.shortcuts import render
from datetime import datetime, timedelta, date, time, timedelta
from io import BytesIO

# Third-party
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.mail import EmailMessage
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.template.loader import get_template
from django.utils import timezone
from django.views.decorators.http import require_POST
from xhtml2pdf import pisa
from django.db.models import ProtectedError

# Local
from .models import Booking, Table
from .forms import (
    BookingForm,
    AvailabilityForm,
    BookingStatusUpdateForm,
    TableForm,
    CustomUserCreationForm,
)

# Debug prints to confirm models.py is loaded correctly
print(
    f"DEBUG VIEWS: Loading models.py from: {os.path.abspath(os.path.join(os.path.dirname(__file__), 'models.py'))}")
# (Note: Using os.path.join and os.path.dirname for robustness in getting models.py path)
try:
    from .models import Booking  # Import again to check its field directly
    table_field = Booking._meta.get_field('table')
    print(
        f"DEBUG VIEWS: Booking.table.on_delete setting: {table_field.on_delete}")
    # _PROTECT is the internal value for PROTECT
    print(
        f"DEBUG VIEWS: Is it PROTECT? {table_field.on_delete == ProtectedError._PROTECT}")
except Exception as e:
    print(f"DEBUG VIEWS: Could not inspect Booking.table.on_delete: {e}")


# Decorator for staff members (assuming you have this defined elsewhere or use is_staff check)
# If this is not defined elsewhere, ensure it's here or in a utils.py
def staff_member_required(view_func):
    def wrapper_func(request, *args, **kwargs):
        if not request.user.is_authenticated or not request.user.is_staff:
            messages.error(
                request, "You are not authorized to view this page.")
            # Or wherever you redirect unauthorized users
            return redirect('home')
        return view_func(request, *args, **kwargs)
    return wrapper_func

def register(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Registration successful. Welcome!")
            return redirect('home')
        else:
            messages.error(
                request, "Registration failed. Please correct the errors below.")
            # important
            return render(request, 'registration/register.html', {'form': form})
    else:
        form = CustomUserCreationForm()
    return render(request, 'registration/register.html', {'form': form})



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

            # Define allowed time range
            opening_time = time(9, 0)   # 9:00 AM
            closing_time = time(22, 0)  # 10:00 PM

            # Check if booking time is outside of allowed interval
            if not (opening_time <= booking_time <= closing_time):
                messages.warning(
                    request, "Bookings can only be made between 9:00 AM and 10:00 PM.")
                return render(request, 'bookings/make_booking.html', {'form': form})

            # Check if the booking is in the past
            if booking_datetime < timezone.now():
                form.add_error('booking_date', "Booking date cannot be in the past.")
                return render(request, 'bookings/make_booking.html', {'form': form})

            # Find tables booked at the exact time
            booked_tables_ids = Booking.objects.filter(
                booking_date=booking_date,
                booking_time=booking_time
            ).values_list('table__id', flat=True)

            # Start with tables that match capacity and aren't booked at that exact time
            available_tables = Table.objects.filter(
                capacity__gte=number_of_guests
            ).exclude(id__in=booked_tables_ids)

            # Further exclude tables booked within 1 hour window
            one_hour_before = (datetime.combine(
                booking_date, booking_time) - timedelta(hours=1)).time()
            one_hour_after = (datetime.combine(
                booking_date, booking_time) + timedelta(hours=1)).time()

            conflicting_bookings = Booking.objects.filter(
                booking_date=booking_date,
                table__in=available_tables,
                booking_time__range=(one_hour_before, one_hour_after)
            )

            conflicting_table_ids = conflicting_bookings.values_list(
                'table__id', flat=True)
            available_tables = available_tables.exclude(
                id__in=conflicting_table_ids).order_by('capacity')

            if available_tables.exists():
                selected_table = available_tables.first()
                try:
                    with transaction.atomic():
                        booking = form.save(commit=False)
                        booking.user = request.user
                        booking.table = selected_table
                        booking.status = 'confirmed'
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
def edit_booking(request, booking_id):
    """Allow a user to edit their existing booking."""
    booking = get_object_or_404(Booking, id=booking_id, user=request.user)

    if request.method == 'POST':
        form = BookingForm(request.POST, instance=booking)
        if form.is_valid():
            booking_date = form.cleaned_data['booking_date']
            booking_time = form.cleaned_data['booking_time']
            number_of_guests = form.cleaned_data['number_of_guests']

            # Combine date and time, then make it timezone-aware
            booking_datetime = datetime.combine(booking_date, booking_time)
            booking_datetime = timezone.make_aware(booking_datetime)

            # Define allowed time range (same as in make_booking)
            opening_time = time(9, 0)
            closing_time = time(22, 0)

            # Check if booking time is outside of allowed interval
            if not (opening_time <= booking_time <= closing_time):
                messages.warning(
                    request, "Bookings can only be made between 9:00 AM and 10:00 PM.")
                return render(request, 'bookings/edit_booking.html', {'form': form, 'booking': booking})

            # Check if the booking is in the past
            if booking_datetime < timezone.now():
                messages.warning(
                    request, "You cannot edit a booking to a past time.")
                return render(request, 'bookings/edit_booking.html', {'form': form, 'booking': booking})

            # Find tables booked at the exact time, excluding the current booking's table
            booked_tables_ids = Booking.objects.filter(
                booking_date=booking_date,
                booking_time=booking_time
            ).exclude(id=booking.id).values_list('table__id', flat=True)

            # Start with tables that match capacity and aren't booked at that exact time
            available_tables = Table.objects.filter(
                capacity__gte=number_of_guests
            ).exclude(id__in=booked_tables_ids)

            # Further exclude tables booked within 1 hour window, excluding the current booking's table
            one_hour_before = (datetime.combine(
                booking_date, booking_time) - timedelta(hours=1)).time()
            one_hour_after = (datetime.combine(
                booking_date, booking_time) + timedelta(hours=1)).time()

            conflicting_bookings = Booking.objects.filter(
                booking_date=booking_date,
                table__in=available_tables,
                booking_time__range=(one_hour_before, one_hour_after)
            ).exclude(id=booking.id)  # Exclude the current booking itself

            conflicting_table_ids = conflicting_bookings.values_list(
                'table__id', flat=True)
            available_tables = available_tables.exclude(
                id__in=conflicting_table_ids).order_by('capacity')

            if available_tables.exists():
                selected_table = available_tables.first()
                try:
                    with transaction.atomic():
                        # Update the existing booking with new data
                        booking.booking_date = booking_date
                        booking.booking_time = booking_time
                        booking.number_of_guests = number_of_guests
                        booking.table = selected_table  # Assign the newly found table
                        booking.save()
                        messages.success(
                            request, f"Your booking for Table {selected_table.number} has been updated successfully!")
                        return redirect('my_bookings')
                except Exception as e:
                    messages.error(
                        request, f"An error occurred during booking update: {e}")
            else:
                messages.warning(
                    request, "No tables available for your requested date, time, and number of guests for this edit.")
        else:
            messages.error(request, "Please correct the errors in the form.")
    else:
        form = BookingForm(instance=booking)

    context = {
        'form': form,
        'booking': booking,
    }
    return render(request, 'bookings/edit_booking.html', context)


# @require_POST
# @login_required
# def cancel_booking(request, booking_id):
#     """Allow a user to cancel their booking."""
#     booking = get_object_or_404(Booking, id=booking_id, user=request.user)

#     # Combine date and time, then make it timezone-aware
#     booking_datetime = datetime.combine(
#         booking.booking_date, booking.booking_time)
#     booking_datetime = timezone.make_aware(booking_datetime)

#     if booking_datetime < timezone.now() + timedelta(hours=2):
#         messages.warning(
#             request, "Bookings cannot be cancelled within 2 hours of the reservation time.")
#     else:
#         booking.delete()
#         messages.success(
#             request, "Your booking has been successfully cancelled.")

#     return redirect('my_bookings')

@require_POST
@login_required
def cancel_booking(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id, user=request.user)

    # Combine date and time and make timezone-aware
    booking_datetime = timezone.make_aware(
        datetime.combine(booking.booking_date, booking.booking_time)
    )

    if booking.status == 'cancelled':
        messages.warning(request, "This booking is already cancelled.")
        return redirect('my_bookings')

    if booking_datetime < timezone.now() + timedelta(hours=2):
        messages.warning(
            request, "Bookings cannot be cancelled within 2 hours of the reservation time.")
        return redirect('my_bookings')

    booking.status = 'cancelled'
    booking.save()
    messages.success(request, "Your booking has been successfully cancelled.")
    return redirect('my_bookings')


# @staff_member_required
# def staff_dashboard(request):
#     """Restaurant staff dashboard overview."""
#     today = timezone.now().date()
#     upcoming_bookings_count = Booking.objects.filter(
#         booking_date__gte=today, status='pending').count()
#     confirmed_today_count = Booking.objects.filter(
#         booking_date=today, status='confirmed').count()
#     total_tables = Table.objects.count()

#     upcoming_active_bookings_count = Booking.objects.filter(
#         booking_date__gte=today,
#         status='pending',
#         # active=True,  # Removed because field does not exist
#     ).count()

#     context = {
#         'upcoming_bookings_count': upcoming_bookings_count,
#         'confirmed_today_count': confirmed_today_count,
#         'total_tables': total_tables,
#         'upcoming_active_bookings_count': upcoming_active_bookings_count,
#     }
#     return render(request, 'bookings/staff_dashboard.html', context)

def check_availability(request):
    """View to check table availability based on date, time, and guests, enforcing a ±2 hour rule."""
    available_tables = []

    if request.method == 'POST':
        form = AvailabilityForm(request.POST)
        if form.is_valid():
            check_date = form.cleaned_data['check_date']
            check_time = form.cleaned_data['check_time']
            num_guests = form.cleaned_data['num_guests']

            # Combine date and time into a datetime object
            requested_datetime = timezone.make_aware(
                datetime.combine(check_date, check_time))
            two_hours_before = (requested_datetime - timedelta(hours=2)).time()
            two_hours_after = (requested_datetime + timedelta(hours=2)).time()

            # Find conflicting bookings within ±2 hours on the same date
            conflicting_bookings = Booking.objects.filter(
                booking_date=check_date,
                booking_time__range=(two_hours_before, two_hours_after),
                status='confirmed'  # Only confirmed bookings block availability
            )


            conflicting_table_ids = conflicting_bookings.values_list(
                'table_id', flat=True)

            # Find available tables that meet guest count and are not conflicted
            available_tables = Table.objects.filter(
                capacity__gte=num_guests
            ).exclude(id__in=conflicting_table_ids).order_by('capacity')

            if not available_tables.exists():
                messages.warning(
                    request, "No tables are available within 2 hours of the selected time.")
            else:
                messages.success(
                    request, f"Found {available_tables.count()} table(s) available.")
        else:
            messages.error(
                request, "Please correct the errors to check availability.")
    else:
        form = AvailabilityForm()

    return render(request, 'bookings/check_availability.html', {
        'form': form,
        'available_tables': available_tables
    })


def staff_dashboard(request):
    # Ensure only staff can access
    if not request.user.is_staff:
        # Redirect or show permission denied as appropriate
        return redirect('login')  # or use permission decorators

    today = timezone.now().date()

    # Filter bookings with status 'pending' or 'confirmed' and date >= today
    upcoming_bookings = Booking.objects.filter(
        booking_date__gte=today,
        status__in=['pending', 'confirmed']
    )

    # Count the number of upcoming active bookings
    upcoming_active_bookings_count = upcoming_bookings.count()

    # Count bookings confirmed for today (optional, based on your context)
    confirmed_today_count = Booking.objects.filter(
        booking_date=today,
        status='confirmed'
    ).count()

    total_tables = Table.objects.count()

    context = {
        'upcoming_active_bookings_count': upcoming_active_bookings_count,
        'confirmed_today_count': confirmed_today_count,
        'total_tables': total_tables,
    }

    return render(request, 'bookings/staff_dashboard.html', context)

# Decorator for staff members (assuming you have this defined elsewhere or use is_staff check)


@staff_member_required
def staff_booking_list(request):
    """List all bookings for staff, with search and filters."""
    bookings_list = Booking.objects.all().order_by('-booking_date', '-booking_time')

    query = request.GET.get('q')
    status_filter = request.GET.get('status')
    date_filter = request.GET.get('date')

    if query:
        bookings_list = bookings_list.filter(
            Q(user__username__icontains=query) |
            Q(table__number__icontains=query) |
            Q(notes__icontains=query)
        )
    if status_filter:
        bookings_list = bookings_list.filter(status=status_filter)
    if date_filter:
        try:
            parsed_date = datetime.strptime(date_filter, '%Y-%m-%d').date()
            bookings_list = bookings_list.filter(booking_date=parsed_date)
        except ValueError:
            messages.error(request, "Invalid date format. Please use YYYY-MM-DD.")
            # Clear the date_filter so it doesn't show invalid value in the form
            date_filter = ''    # Reset to empty

    paginator = Paginator(bookings_list, 10)  # Show 10 bookings per page
    page = request.GET.get('page')
    try:
        bookings = paginator.page(page)
    except PageNotAnInteger:
        bookings = paginator.page(1)
    except EmptyPage:
        bookings = paginator.page(paginator.num_pages)

    context = {
        'bookings': bookings,
        'query': query,
        'status_filter': status_filter,
        'date_filter': date_filter,
        'status_choices': Booking.BOOKING_STATUS_CHOICES,  # Pass choices to template
        'active_tab': 'bookings',
    }
    return render(request, 'bookings/staff_booking_list.html', {
        'bookings': bookings,
        'query': query,
        'status_filter': status_filter,
        'date_filter': date_filter,
        'status_choices': Booking.BOOKING_STATUS_CHOICES,
        'active_tab': 'bookings',
    })


@staff_member_required
def staff_booking_detail(request, booking_id):
    """View and update details of a specific booking."""
    booking = get_object_or_404(Booking, id=booking_id)

    if request.method == 'POST':
        form = BookingStatusUpdateForm(request.POST, instance=booking)
        if form.is_valid():
            form.save()
            messages.success(request, "Booking status updated successfully!")
            return redirect('staff_booking_list')
        else:
            messages.error(request, "Error updating booking status.")
    else:
        form = BookingStatusUpdateForm(instance=booking)

    context = {
        'booking': booking,
        'form': form,
    }
    return render(request, 'bookings/staff_booking_detail.html', context)


@staff_member_required
def staff_table_list(request):
    """
    Displays a list of all restaurant tables and allows staff to add new ones.
    """
    tables = Table.objects.all().order_by('number')

    if request.method == 'POST':
        form = TableForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(
                request, f"Table {form.cleaned_data['number']} added successfully!")
            return redirect('staff_table_list')
        else:
            messages.error(
                request, "Please correct the errors in the form when adding a table.")
    else:
        form = TableForm()  # For GET request, provide an empty form

    context = {
        'tables': tables,
        'form': form,
        'active_tab': 'tables',
    }
    return render(request, 'bookings/staff_table_list.html', context)


@staff_member_required
def staff_table_edit(request, table_id):
    """Edit a specific restaurant table."""
    table = get_object_or_404(Table, id=table_id)

    if request.method == 'POST':
        form = TableForm(request.POST, instance=table)
        if form.is_valid():
            form.save()
            messages.success(
                request, f"Table {table.number} updated successfully!")
            return redirect('staff_table_list')
        else:
            messages.error(request, "Please correct the errors in the form.")
    else:
        form = TableForm(instance=table)

    context = {
        'form': form,
        'table': table,
        'active_tab': 'tables',
    }
    return render(request, 'bookings/staff_table_edit.html', context)


@staff_member_required
@require_POST
def staff_table_delete(request, table_id):
    """
    Deletes a specific restaurant table. Protected if it has active bookings.
    """
    print(
        f"\n--- DEBUG VIEWS: Entering staff_table_delete for table_id: {table_id} ---")

    try:
        table = get_object_or_404(Table, pk=table_id)
        print(f"DEBUG VIEWS: Retrieved table: {table.number} (PK: {table.pk})")

        # Check related bookings BEFORE the delete attempt
        related_bookings = Booking.objects.filter(table=table)
        print(
            f"DEBUG VIEWS: Number of related bookings for table {table.pk}: {related_bookings.count()}")
        if related_bookings.exists():
            print(
                f"DEBUG VIEWS: Related booking PKs: {[b.pk for b in related_bookings]}")
            print(
                f"DEBUG VIEWS: Related booking statuses: {[b.status for b in related_bookings]}")
        else:
            print(
                f"DEBUG VIEWS: No related bookings found for table {table.pk}.")

        # This is the line that should raise ProtectedError if relationships exist and PROTECT is on
        table.delete()

        print(
            f"DEBUG VIEWS: Table {table.pk} DELETED successfully (THIS SHOULD NOT HAPPEN IF PROTECTED!).")
        messages.success(
            request, f"Table {table.number} deleted successfully!")
        return redirect('staff_table_list')  # Returns 302

    except ProtectedError as e:
        print(
            f"DEBUG VIEWS: ProtectedError CAUGHT for Table {table_id}. Error: {e}")
        messages.error(
            request, "This table cannot be deleted as it has active bookings.")
        # Render the staff table list page with the error message
        tables = Table.objects.all().order_by('number')
        form = TableForm()
        context = {'tables': tables, 'form': form, 'active_tab': 'tables'}
        # Returns 200
        return render(request, 'bookings/staff_table_list.html', context)

    except Exception as e:
        # Catch any other unexpected errors during the process
        print(
            f"DEBUG VIEWS: An UNEXPECTED ERROR occurred for Table {table_id}: {e}")
        messages.error(
            request, f"An unexpected error occurred while deleting the table: {e}")
        # Redirect to list page even for unexpected errors
        return redirect('staff_table_list')
