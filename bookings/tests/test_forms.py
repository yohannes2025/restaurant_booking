# bookings/tests/test_forms.py
from django.test import TestCase
from django import forms
from datetime import date, time, timedelta, datetime
from django.utils import timezone
from django.contrib.auth import get_user_model
from bookings.forms import (
    CustomUserCreationForm,
    BookingForm,
    AvailabilityForm,
    BookingStatusUpdateForm,
    TableForm
)
from bookings.models import Booking, Table

User = get_user_model()


class CustomUserCreationFormTest(TestCase):
    """
    Tests for the CustomUserCreationForm.
    """

    def test_valid_form(self):
        form = CustomUserCreationForm(data={
            'username': 'newuser',
            'email': 'newuser@example.com',
            'password1': 'StrongP@ssw0rd',
            'password2': 'StrongP@ssw0rd',
        })
        self.assertTrue(form.is_valid())
        user = form.save()
        self.assertEqual(user.username, 'newuser')
        self.assertEqual(user.email, 'newuser@example.com')
        self.assertTrue(user.check_password('StrongP@ssw0rd'))

    def test_password_mismatch(self):
        form_data = {
            'username': 'testuser',
            'email': 'test@example.com',
            'password1': 'password123',
            'password2': 'differentpassword',
        }
        form = CustomUserCreationForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn("password fields", form.errors["password2"][0])

    def test_duplicate_username(self):
        User.objects.create_user(username='existinguser', password='password')
        form = CustomUserCreationForm(data={
            'username': 'existinguser',
            'email': 'some@example.com',
            'password1': 'pass',
            'password2': 'pass',
        })
        self.assertFalse(form.is_valid())
        self.assertIn('username', form.errors)
        self.assertIn("A user with that username already exists.",
                      form.errors['username'])


class BookingFormTest(TestCase):
    def test_booking_form_past_date_time(self):
        # Create a booking date/time in the past
        past_date = date.today() - timedelta(days=1)
        past_time = time(12, 0)  # Noon

        form_data = {
            'booking_date': past_date,
            'booking_time': past_time,
            'number_of_guests': 2,
            'notes': 'Test past booking',
        }
        form = BookingForm(data=form_data)

        # Should be invalid because date/time is in the past
        self.assertFalse(form.is_valid())

        # Check error is under '__all__' because clean() raises ValidationError
        self.assertIn('booking_date', form.errors)


        self.assertIn('Booking date cannot be in the past.',
              form.errors['booking_date'])


    def test_booking_form_time_out_of_range(self):
        # Time before 9 AM
        form_data = {
            'booking_date': date.today() + timedelta(days=1),
            'booking_time': time(8, 0),
            'number_of_guests': 2,
            'notes': '',
        }
        form = BookingForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('booking_time', form.errors)
        self.assertIn(
            'Booking time must be between 9:00 AM and 10:00 PM.', form.errors['booking_time'])

    def test_booking_form_zero_guests(self):
        form_data = {
            'booking_date': date.today() + timedelta(days=1),
            'booking_time': time(12, 0),
            'number_of_guests': 0,
            'notes': '',
        }
        form = BookingForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('number_of_guests', form.errors)
        self.assertIn('Number of guests must be at least 1.',
                      form.errors['number_of_guests'])


class AvailabilityFormTest(TestCase):
    """
    Tests for the AvailabilityForm.
    """

    def test_valid_availability_form_data(self):
        future_date = date.today() + timedelta(days=5)
        form_data = {
            'check_date': future_date.isoformat(),
            'check_time': '19:00',
            'num_guests': 2,
        }
        form = AvailabilityForm(data=form_data)
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data['check_date'], future_date)
        self.assertEqual(form.cleaned_data['check_time'], time(19, 0))
        self.assertEqual(form.cleaned_data['num_guests'], 2)

    def test_availability_form_past_date_time(self):
        past_date = date.today() - timedelta(days=1)
        past_time = (timezone.now() - timedelta(minutes=10)).time()

        # Test past date
        form_data_past_date = {
            'check_date': past_date.isoformat(),
            'check_time': '12:00',
            'num_guests': 2,
        }
        form = AvailabilityForm(data=form_data_past_date)
        self.assertFalse(form.is_valid())
        self.assertIn('__all__', form.errors)  # Global error
        self.assertIn(
            "You cannot check availability for a past date and time.", form.errors['__all__'])

        # Test past time on current date
        form_data_past_time_today = {
            'check_date': date.today().isoformat(),
            'check_time': past_time.strftime('%H:%M'),
            'num_guests': 2,
        }
        form = AvailabilityForm(data=form_data_past_time_today)
        self.assertFalse(form.is_valid())
        self.assertIn('__all__', form.errors)
        self.assertIn(
            "You cannot check availability for a past date and time.", form.errors['__all__'])
        
        def clean(self):
            cleaned_data = super().clean()
            date_time = cleaned_data.get('date_time')
            if date_time and date_time < timezone.now():
                self.add_error('date_time', 'Date and time cannot be in the past.')

    def test_availability_form_time_out_of_range(self):
        future_date = date.today() + timedelta(days=5)

        # Before opening
        form_data_early = {
            'check_date': future_date.isoformat(),
            'check_time': '08:00',
            'num_guests': 2,
        }
        form = AvailabilityForm(data=form_data_early)
        self.assertFalse(form.is_valid())
        self.assertIn('__all__', form.errors)
        self.assertIn("Restaurant is open from 9:00 AM to 10:00 PM.",
                      form.errors['__all__'])

        # After closing
        form_data_late = {
            'check_date': future_date.isoformat(),
            'check_time': '23:00',
            'num_guests': 2,
        }
        form = AvailabilityForm(data=form_data_late)
        self.assertFalse(form.is_valid())
        self.assertIn('__all__', form.errors)
        self.assertIn("Restaurant is open from 9:00 AM to 10:00 PM.",
                      form.errors['__all__'])

    def test_availability_form_zero_guests(self):
        future_date = date.today() + timedelta(days=5)
        form_data = {
            'check_date': future_date.isoformat(),
            'check_time': '19:00',
            'num_guests': 0,
        }
        form = AvailabilityForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('num_guests', form.errors)
        self.assertIn("Number of guests must be at least 1.",
                      form.errors['num_guests'])


class BookingStatusUpdateFormTest(TestCase):
    """
    Tests for the BookingStatusUpdateForm (for staff).
    """
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username='stafftest', password='password')
        cls.table = Table.objects.create(number=1, capacity=4)
        cls.booking = Booking.objects.create(
            user=cls.user,
            table=cls.table,
            booking_date=date.today() + timedelta(days=1),
            booking_time=time(12, 0),
            number_of_guests=2,
            status='pending'
        )

    def test_valid_status_update_form(self):
        form_data = {
            'status': 'confirmed',
            'notes': 'Guest called to confirm.'
        }
        form = BookingStatusUpdateForm(data=form_data, instance=self.booking)
        self.assertTrue(form.is_valid())
        updated_booking = form.save()
        self.assertEqual(updated_booking.status, 'confirmed')
        self.assertEqual(updated_booking.notes, 'Guest called to confirm.')

    def test_invalid_status_update_form_choice(self):
        form_data = {
            'status': 'invalid_status',  # Invalid choice
            'notes': 'Some notes.'
        }
        form = BookingStatusUpdateForm(data=form_data, instance=self.booking)
        self.assertFalse(form.is_valid())
        self.assertIn('status', form.errors)
        self.assertIn(
            "Select a valid choice. invalid_status is not one of the available choices.", form.errors['status'])


class TableFormTest(TestCase):
    """
    Tests for the TableForm (for staff).
    """

    def test_valid_table_form_data(self):
        form_data = {
            'number': 101,
            'capacity': 8,
        }
        form = TableForm(data=form_data)
        self.assertTrue(form.is_valid())
        table = form.save()
        self.assertEqual(table.number, 101)
        self.assertEqual(table.capacity, 8)
        self.assertEqual(Table.objects.count(), 1)

    def test_duplicate_table_number(self):
        Table.objects.create(number=101, capacity=4)
        form_data = {
            'number': 101,
            'capacity': 6,
        }
        form = TableForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('number', form.errors)
        self.assertIn(
            "Table with this Table Number already exists.", form.errors['number'])

    def test_table_form_zero_capacity(self):
        form_data = {
            'number': 102,
            'capacity': 0,  # Invalid capacity
        }
        form = TableForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('capacity', form.errors)
        self.assertIn(
            "Ensure this value is greater than or equal to 1.", form.errors['capacity'])
