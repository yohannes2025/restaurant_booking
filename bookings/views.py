# bookings/views.py
from django.shortcuts import render, redirect, get_object_or_404
from .forms import BookingForm, AvailabilityForm, BookingStatusUpdateForm
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.utils import timezone
from datetime import datetime, timedelta, date, time
from django.contrib.admin.views.decorators import staff_member_required 
from django.db.models import Q  # For search/filter
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

from .models import Booking, Table
from .forms import BookingForm, Booking

from django.shortcuts import redirect

# For PDF generation
from django.template.loader import get_template
from django.http import HttpResponse
from io import BytesIO
from xhtml2pdf import pisa
from django.core.mail import EmailMessage

from .models import Booking, Table
from .forms import BookingForm, AvailabilityForm

from .forms import BookingForm, AvailabilityForm, BookingStatusUpdateForm, TableForm

from django.contrib.auth import login
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.utils import timezone
from .forms import TableForm
from .forms import CustomUserCreationForm



def register(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            # Automatically log in the user after registration
            login(request, user)
            messages.success(request, "Registration successful. Welcome!")
            return redirect('home')  # Redirect to home page or a profile page
        else:
            # Add error messages to the form for display in template
            messages.error(
                request, "Registration failed. Please correct the errors below.")
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
                messages.warning(
                    request, "You cannot make a booking in the past.")
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
def cancel_booking(request, booking_id):
    """Allow a user to cancel their booking."""
    booking = get_object_or_404(Booking, id=booking_id, user=request.user)

    # Combine date and time, then make it timezone-aware
    booking_datetime = datetime.combine(
        booking.booking_date, booking.booking_time)
    booking_datetime = timezone.make_aware(booking_datetime)

    if booking_datetime < timezone.now() + timedelta(hours=2):
        messages.warning(
            request, "Bookings cannot be cancelled within 2 hours of the reservation time.")
    else:
        booking.delete()
        messages.success(
            request, "Your booking has been successfully cancelled.")

    return redirect('my_bookings')


# Staff Dashboard Views
@staff_member_required
def staff_dashboard(request):
    """Restaurant staff dashboard overview."""
    today = timezone.now().date()
    upcoming_bookings_count = Booking.objects.filter(
        booking_date__gte=today, status='pending').count()
    confirmed_today_count = Booking.objects.filter(
        booking_date=today, status='confirmed').count()
    total_tables = Table.objects.count()

    context = {
        'upcoming_bookings_count': upcoming_bookings_count,
        'confirmed_today_count': confirmed_today_count,
        'total_tables': total_tables,
    }
    return render(request, 'bookings/staff_dashboard.html', context)


def check_availability(request):
    """View to check table availability based on date, time, and guests."""
    available_tables = []
    if request.method == 'POST':
        form = AvailabilityForm(request.POST)
        if form.is_valid():
            check_date = form.cleaned_data['check_date']
            check_time = form.cleaned_data['check_time']
            num_guests = form.cleaned_data['num_guests']

            # Find tables already booked at the exact date and time
            booked_tables_ids = Booking.objects.filter(
                booking_date=check_date,
                booking_time=check_time
            ).values_list('table__id', flat=True)

            # Find tables that can accommodate the guests and are not booked
            available_tables = Table.objects.filter(
                capacity__gte=num_guests
            ).exclude(id__in=booked_tables_ids).order_by('capacity')

            if not available_tables.exists():
                messages.warning(
                    request, "No tables are available for the selected criteria.")
            else:
                messages.success(
                    request, f"Found {available_tables.count()} table(s) available.")
        else:
            messages.error(
                request, "Please correct the errors to check availability.")
    else:
        form = AvailabilityForm()

    context = {
        'form': form,
        'available_tables': available_tables,
    }
    return render(request, 'bookings/check_availability.html', context)


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
            # Assuming date_filter comes in YYYY-MM-DD format
            parsed_date = datetime.strptime(date_filter, '%Y-%m-%d').date()
            bookings_list = bookings_list.filter(booking_date=parsed_date)
        except ValueError:
            messages.error(request, "Invalid date format.")

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
    return render(request, 'bookings/staff_booking_list.html', context)


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
    """List and manage restaurant tables."""
    tables = Table.objects.all().order_by('number')

    if request.method == 'POST':
        form = TableForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "New table added successfully!")
            return redirect('staff_table_list')
        else:
            messages.error(request, "Please correct the errors in the form.")
    else:
        form = TableForm()

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
        form = BookingForm(request.POST, instance=table)
        # NOTE: BookingForm is probably not the right form for editing tables.
        # You should create a separate TableForm for editing tables.
        # For now, assuming you have a TableForm:
        form = TableForm(request.POST, instance=table)

        if form.is_valid():
            form.save()
            messages.success(
                request, f"Table {table.number} updated successfully!")
            return redirect('staff_table_list')
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = TableForm(instance=table)

    context = {
        'form': form,
        'table': table,
    }
    return render(request, 'bookings/staff_table_edit.html', context)


@staff_member_required
def staff_table_delete(request, table_id):
    table = get_object_or_404(Table, id=table_id)
    if request.method == "POST":
        table.delete()
        messages.success(
            request, f"Table {table.number} deleted successfully.")
        return redirect('staff_table_list')
    return render(request, 'bookings/staff_table_confirm_delete.html', {'table': table})
