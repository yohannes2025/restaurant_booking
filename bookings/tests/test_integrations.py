# bookings/tests/test_integrations.py
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from datetime import date, time, timedelta, datetime
from django.utils import timezone
from bookings.models import Table, Booking
from unittest.mock import patch


User = get_user_model()


class UserBookingFlowIntegrationTest(TestCase):
    """
    Integrations tests for a typical user booking journey.
    """
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username='integration_user', password='password123')
        cls.table1 = Table.objects.create(number=1, capacity=2)
        cls.table2 = Table.objects.create(number=2, capacity=4)
        cls.future_date = date.today() + timedelta(days=10)
        cls.booking_time = time(19, 0)  # 7 PM

    def setUp(self):
        self.client.login(username='integration_user', password='password123')
        # Mock timezone.now for consistent past/future checks
        self.mock_now = datetime.combine(date.today(), time(12, 0))
        self.patcher = patch('django.utils.timezone.now',
                             return_value=timezone.make_aware(self.mock_now))
        self.mock_timezone_now = self.patcher.start()

    def tearDown(self):
        self.patcher.stop()

    def test_full_booking_flow_create_edit_cancel(self):
        """
        Tests the complete cycle of creating, editing, and cancelling a booking.
        """
        # --- Step 1: Create a Booking ---
        initial_booking_count = Booking.objects.count()
        form_data_create = {
            'booking_date': self.future_date.isoformat(),
            'booking_time': self.booking_time.strftime('%H:%M'),
            'number_of_guests': 2,
            'notes': 'Initial booking notes',
        }
        response_create = self.client.post(
            reverse('make_booking'), form_data_create, follow=True)
        # Check successful creation and redirection
        # follow=True resolves to the final page
        self.assertEqual(response_create.status_code, 200)
        self.assertTemplateUsed(response_create, 'bookings/my_bookings.html')
        self.assertContains(
            response_create, "Your booking for Table 1 has been confirmed!")
        self.assertEqual(Booking.objects.count(), initial_booking_count + 1)
        booking = Booking.objects.first()
        self.assertEqual(booking.notes, 'Initial booking notes')
        self.assertEqual(booking.table, self.table1)
        self.assertEqual(booking.status, 'confirmed')

        # Check booking is displayed on 'my_bookings' page
        self.assertContains(response_create, "Initial booking notes")
        formatted_date = self.future_date.strftime(
            '%B %d, %Y')  # e.g. "June 16, 2025"
        self.assertContains(response_create, formatted_date)


        # --- Step 2: Edit the Booking ---
        # Get the current ID of the booking
        booking_id = booking.pk
        new_guests = 3
        new_time = time(20, 0)  # 8 PM

        form_data_edit = {
            'booking_date': self.future_date.isoformat(),
            'booking_time': new_time.strftime('%H:%M'),
            'number_of_guests': new_guests,
            'notes': 'Updated notes for more guests',
        }
        response_edit = self.client.post(
            reverse('edit_booking', args=[booking_id]), form_data_edit, follow=True)

        # Check successful edit and redirection
        self.assertEqual(response_edit.status_code, 200)
        self.assertTemplateUsed(response_edit, 'bookings/my_bookings.html')
        self.assertContains(
            response_edit, "Your booking for Table 2 has been updated successfully!")

        booking.refresh_from_db()
        self.assertEqual(booking.number_of_guests, new_guests)
        self.assertEqual(booking.booking_time, new_time)
        self.assertEqual(booking.notes, 'Updated notes for more guests')
        # Table should have changed due to capacity for 3 guests
        self.assertEqual(booking.table, self.table2)

        # Check updated booking is displayed on 'my_bookings' page
        self.assertContains(response_edit, "Updated notes for more guests")
        self.assertNotContains(response_edit, "Initial booking notes")

        # --- Step 3: Cancel the Booking ---
        # Ensure the booking is not too close to the current time for cancellation
        # (Our mock_now is far enough from future_date for this to pass)
        response_cancel = self.client.post(
            reverse('cancel_booking', args=[booking_id]), follow=True)

        # Check successful cancellation and redirection
        self.assertEqual(response_cancel.status_code, 200)
        self.assertTemplateUsed(response_cancel, 'bookings/my_bookings.html')
        self.assertContains(
            response_cancel, "Your booking has been successfully cancelled.")

        booking.refresh_from_db()
        self.assertEqual(booking.status, 'cancelled')

        # Check cancelled booking status is displayed on 'my_bookings' page
        self.assertContains(response_cancel, "cancelled")
        # Still shows notes
        self.assertContains(response_cancel, "Updated notes for more guests")

    def test_booking_and_availability_check_interplay(self):
        """
        Tests that booking a table correctly affects availability checks.
        """
        # Step 1: Check availability for a future slot (should show tables)
        check_date = self.future_date
        check_time = self.booking_time
        form_data_check = {
            'check_date': check_date.isoformat(),
            'check_time': check_time.strftime('%H:%M'),
            'num_guests': 2,
        }
        response_initial_check = self.client.post(
            reverse('check_availability'), form_data_check)
        self.assertEqual(response_initial_check.status_code, 200)
        # table1 and table2 available for 2 guests
        self.assertContains(response_initial_check,
                            "Found 2 table(s) available.")

        # Step 2: Make a booking that occupies one table
        form_data_book = {
            'booking_date': check_date.isoformat(),
            'booking_time': check_time.strftime('%H:%M'),
            'number_of_guests': 2,
            'notes': 'Booking one table',
        }
        # No need to follow, just make the booking
        self.client.post(reverse('make_booking'), form_data_book)

        # Step 3: Check availability again for the same slot (should show fewer tables)
        response_after_book_check = self.client.post(
            reverse('check_availability'), form_data_check)
        self.assertEqual(response_after_book_check.status_code, 200)
        # Only table2 should be available for 2 guests
        self.assertContains(response_after_book_check,
                            "Found 1 table(s) available.")
        self.assertContains(response_after_book_check,
                            f"Table {self.table2.number}")
        available_section = response_after_book_check.content.decode().split(
            "Available Tables:")[-1]
        self.assertNotIn("Table 1", available_section)


        # Step 4: Cancel the booking
        booking = Booking.objects.first()
        response_cancel = self.client.post(
            reverse('cancel_booking', args=[booking.pk]))

        # Step 5: Check availability one last time (should show tables are available again)
        response_after_cancel_check = self.client.post(
            reverse('check_availability'), form_data_check)
        self.assertEqual(response_after_cancel_check.status_code, 200)
        # Both tables available again
        self.assertContains(response_after_cancel_check,
                            "Found 2 table(s) available.")
