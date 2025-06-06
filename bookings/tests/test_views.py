# bookings/tests/test_views.py
from datetime import time
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from datetime import date, time, timedelta, datetime
from django.utils import timezone
from bookings.models import Table, Booking
# For mocking timezone.now() if precise time control is needed
from unittest.mock import patch
from datetime import timedelta


User = get_user_model()


class PublicViewsTest(TestCase):
    """
    Tests for public views accessible to all users.
    """

    def setUp(self):
        self.client = Client()

    def test_home_view(self):
        """
        Test that the home view renders correctly.
        """
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'bookings/home.html')

    def test_register_view_GET(self):
        """
        Test that the register view renders the form on GET request.
        """
        response = self.client.get(reverse('register'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'registration/register.html')
        self.assertIn('form', response.context)

    def test_register_view_POST_success(self):
        """
        Test successful user registration and redirection.
        """
        initial_user_count = User.objects.count()
        response = self.client.post(reverse('register'), {
            'username': 'newuser_reg',
            'email': 'newuser_reg@example.com',
            'password1': 'SecureP@ss1',
            'password2': 'SecureP@ss1',
        })
        # Should redirect after login
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('home'))
        self.assertEqual(User.objects.count(), initial_user_count + 1)
        user = User.objects.get(username='newuser_reg')
        self.assertTrue(user.is_authenticated)  # User should be logged in

    def test_register_view_POST_failure(self):
        """
        Test failed user registration (e.g., password mismatch).
        """
        initial_user_count = User.objects.count()
        response = self.client.post(reverse('register'), {
            'username': 'failuser',
            'email': 'fail@example.com',
            'password1': 'pass1',
            'password2': 'pass2',
        })

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'registration/register.html')
        self.assertIn('form', response.context)

        # Extract the form from the response context
        form = response.context['form']

        # Now assert the form error
        self.assertFormError(form, 'password2', "The two password fields didn’t match.")
        self.assertEqual(User.objects.count(), initial_user_count)


class AuthenticatedViewsTest(TestCase):
    """
    Tests for views requiring user authentication.
    """
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username='activeuser', password='password123')
        cls.table1 = Table.objects.create(number=1, capacity=2)
        cls.table2 = Table.objects.create(number=2, capacity=4)
        cls.future_date = date.today() + timedelta(days=7)
        cls.booking_time = time(19, 0)  # 7 PM

    def setUp(self):
        self.client.login(username='activeuser', password='password123')
        # Reset current time for consistent testing of past/future bookings
        self.mock_now = datetime.combine(
            date.today(), time(12, 0))  # Mid-day today
        self.patcher = patch('django.utils.timezone.now',
                             return_value=timezone.make_aware(self.mock_now))
        self.mock_timezone_now = self.patcher.start()

    def tearDown(self):
        self.patcher.stop()
    
    def test_make_booking_GET_authenticated(self):
        """
        Test GET request to make_booking view for authenticated user.
        """
        response = self.client.get(reverse('make_booking'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'bookings/make_booking.html')
        self.assertIn('form', response.context)

    def test_make_booking_GET_unauthenticated(self):
        """
        Test GET request to make_booking view for unauthenticated user (should redirect).
        """
        self.client.logout()
        response = self.client.get(reverse('make_booking'))
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(
            response, f"/accounts/login/?next={reverse('make_booking')}")

    def test_make_booking_POST_success(self):
        self.client.login(username='testuser', password='password')
        data = {
            'booking_date': (timezone.now() + timedelta(days=1)).date(),
            'booking_time': '18:00',
            'number_of_guests': 2,
            'notes': 'Window seat',
            'table': self.table1.id
        }
        response = self.client.post(reverse('make_booking'), data, follow=True)
        self.assertEqual(response.status_code, 200)
        booking = Booking.objects.get(user=self.user)
        self.assertEqual(booking.status, 'confirmed')  # Match your view logic

    def test_make_booking_POST_past_date_time(self):
        past_date = (timezone.now() - timedelta(days=1)).date()
        data = {
            'booking_date': past_date,
            'booking_time': time(12, 0),
            'number_of_guests': 2,
            'notes': 'Test past booking',
        }
        response = self.client.post(reverse('make_booking'), data)

        # The form should be re-rendered with errors, status code 200
        self.assertEqual(response.status_code, 200)

        form = response.context['form']

        # Check that 'booking_date' field has the expected error message
        self.assertIn('booking_date', form.errors)
        self.assertIn('Booking date cannot be in the past.',
                  form.errors['booking_date'])


    def test_make_booking_POST_no_tables_available(self):
        """
        Test booking creation when no tables are available.
        """
        # Book table1
        Booking.objects.create(
            user=self.user, table=self.table1,
            booking_date=self.future_date, booking_time=self.booking_time, number_of_guests=2, status='confirmed'
        )
        # Book table2
        Booking.objects.create(
            user=self.user, table=self.table2,
            booking_date=self.future_date, booking_time=self.booking_time, number_of_guests=4, status='confirmed'
        )
        initial_booking_count = Booking.objects.count()  # Should be 2 now

        form_data = {
            'booking_date': self.future_date.isoformat(),
            'booking_time': self.booking_time.strftime('%H:%M'),
            'number_of_guests': 3,  # Needs capacity 3, but both tables are booked
        }
        response = self.client.post(reverse('make_booking'), form_data)
        self.assertEqual(response.status_code, 200)  # Should re-render form
        self.assertTemplateUsed(response, 'bookings/make_booking.html')
        self.assertContains(
            response, "No tables available for your requested date, time, and number of guests.")
        self.assertEqual(Booking.objects.count(), initial_booking_count)  # No new booking


    def test_my_bookings_view_display(self):
        """
        Test that a user's bookings are displayed correctly.
        """
        # Create a past booking for the user
        past_booking_date = date.today() - timedelta(days=5)
        past_booking_time = time(10, 0)
        Booking.objects.create(
            user=self.user, table=self.table1, booking_date=past_booking_date,
            booking_time=past_booking_time, number_of_guests=2, status='Completed'
        )
        # Create an upcoming booking for the user
        upcoming_booking_date = date.today() + timedelta(days=5)
        upcoming_booking_time = time(18, 0)
        upcoming_booking = Booking.objects.create(
            user=self.user, table=self.table2, booking_date=upcoming_booking_date,
            booking_time=upcoming_booking_time, number_of_guests=3, status='pending'
        )
        # Create a booking for another user (should not be displayed)
        other_user = User.objects.create_user(
            username='otheruser', password='password')
        Booking.objects.create(
            user=other_user, table=self.table1, booking_date=upcoming_booking_date,
            booking_time=upcoming_booking_time, number_of_guests=1, status='confirmed'
        )

        response = self.client.get(reverse('my_bookings'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'bookings/my_bookings.html')
        self.assertIn('upcoming_bookings', response.context)
        self.assertIn('past_bookings', response.context)

        self.assertEqual(len(response.context['upcoming_bookings']), 1)
        self.assertEqual(
            response.context['upcoming_bookings'][0], upcoming_booking)
        self.assertContains(response, f"Table {upcoming_booking.table.number}")
        self.assertContains(response, "Pending")

        self.assertEqual(len(response.context['past_bookings']), 1)
        self.assertContains(response, "Table 1")
        self.assertContains(response, "Completed")

        # Ensure other user's booking isn't shown
        self.assertNotContains(response, "otheruser")
    
    def test_edit_booking_GET(self):
        """
        Test GET request to edit_booking view.
        """
        booking = Booking.objects.create(
            user=self.user, table=self.table1,
            booking_date=self.future_date, booking_time=self.booking_time, number_of_guests=2
        )
        response = self.client.get(reverse('edit_booking', args=[booking.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'bookings/edit_booking.html')
        self.assertIn('form', response.context)
        self.assertEqual(response.context['booking'], booking)
        self.assertEqual(response.context['form'].instance, booking)

    def test_edit_booking_GET_unauthorized(self):
        """
        Test GET request to edit_booking for a booking not owned by the user.
        """
        other_user = User.objects.create_user(
            username='other_guy', password='pass')
        booking_other = Booking.objects.create(
            user=other_user, table=self.table1,
            booking_date=self.future_date, booking_time=self.booking_time, number_of_guests=2
        )
        response = self.client.get(
            reverse('edit_booking', args=[booking_other.pk]))
        # Should return 404 if not found for user
        self.assertEqual(response.status_code, 404)

    def test_edit_booking_POST_success(self):
        booking = Booking.objects.create(
            user=self.user,
            table=self.table1,
            booking_date=self.future_date,
            booking_time=self.booking_time,
            number_of_guests=2,
            notes="Initial notes"
        )

        new_guests = 3
        new_time = time(20, 0)  # 8 PM

        url = reverse('edit_booking', kwargs={'booking_id': booking.id})
        form_data = {
            'booking_date': self.future_date.isoformat(),
            'booking_time': new_time.strftime('%H:%M'),
            'number_of_guests': new_guests,
            'notes': 'Updated notes for 3 people',
        }

        response = self.client.post(url, form_data, follow=False)

        self.assertEqual(response.status_code, 302)  # Expect redirect
        self.assertRedirects(response, reverse('my_bookings'))

        booking.refresh_from_db()
        self.assertEqual(booking.number_of_guests, new_guests)
        self.assertEqual(booking.booking_time, new_time)
        self.assertEqual(booking.notes, 'Updated notes for 3 people')

    def test_cancel_booking_POST_success(self):
        """
        Test successful booking cancellation (soft-delete by setting status).
        """
        booking = Booking.objects.create(
            user=self.user, table=self.table1,
            booking_date=timezone.now().date() + timedelta(days=1),
            booking_time=(timezone.now() + timedelta(hours=3)).time(),
            number_of_guests=2, status='pending'
        )
        url = reverse('cancel_booking', kwargs={'booking_id': booking.id})
        response = self.client.post(url, follow=True)

        # Check redirection
        self.assertRedirects(response, reverse('my_bookings'))

        # Check status updated (soft-delete)
        booking.refresh_from_db()
        self.assertEqual(booking.status, 'cancelled')

        # Check message
        messages = list(response.context['messages'])
        self.assertTrue(any("successfully cancelled" in str(m) for m in messages))


        
    def test_cancel_booking_POST_too_close_to_time(self):
        """
        Test cancellation denied if too close to reservation time.
        """
        # Create a booking that is 1 hour from now
        soon_booking_datetime = timezone.now() + timedelta(hours=1)
        booking = Booking.objects.create(
            user=self.user, table=self.table1,
            booking_date=soon_booking_datetime.date(),
            booking_time=soon_booking_datetime.time(),
            number_of_guests=2, status='pending'
        )
        url = reverse('cancel_booking', kwargs={'booking_id': booking.id})
        response = self.client.post(url, follow=True)
        self.assertEqual(response.status_code, 200)  # Still redirects
        self.assertRedirects(response, reverse('my_bookings'))
        booking.refresh_from_db()
        self.assertEqual(booking.status, 'pending')  # Status should not change
        messages = list(response.context['messages'])
        self.assertEqual(len(messages), 1)
        self.assertEqual(str(
            messages[0]), "Bookings cannot be cancelled within 2 hours of the reservation time.")

    def test_cancel_booking_POST_already_cancelled(self):
        """
        Test cancellation of an already cancelled booking.
        """
        booking = Booking.objects.create(
            user=self.user,
            table=self.table1,
            booking_date=(timezone.now() + timedelta(days=1)).date(),
            booking_time=(timezone.now() + timedelta(days=1)).time(),
            number_of_guests=2,
            status='cancelled'
        )
        url = reverse('cancel_booking', args=[booking.pk])
        response = self.client.post(url, follow=False)

        # This must be 302 because the view should redirect
        self.assertEqual(response.status_code, 302)

        # Optional: follow the redirect and check messages if needed
        response = self.client.post(url, follow=True)
        messages = list(response.context['messages'])
        self.assertIn("already cancelled", str(messages[0]))


    def test_check_availability_GET(self):
        """
        Test GET request to check_availability view.
        """
        response = self.client.get(reverse('check_availability'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'bookings/check_availability.html')
        self.assertIn('form', response.context)
        self.assertIn('available_tables', response.context)
        self.assertEqual(len(response.context['available_tables']), 0) # No tables should be shown initially

    def test_check_availability_POST_found_tables(self):
        """
        Test finding available tables.
        """
        # Create a booking to make table1 unavailable
        Booking.objects.create(
            user=self.user, table=self.table1,
            booking_date=self.future_date, booking_time=self.booking_time, number_of_guests=2, status='confirmed'
        )
        form_data = {
            'check_date': self.future_date.isoformat(),
            'check_time': self.booking_time.strftime('%H:%M'),
            'num_guests': 3, # Needs table2 (capacity 4), table1 is booked
        }
        response = self.client.post(reverse('check_availability'), form_data)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'bookings/check_availability.html')
        self.assertIn('available_tables', response.context)
        self.assertEqual(len(response.context['available_tables']), 1)
        self.assertEqual(response.context['available_tables'][0], self.table2)
        self.assertContains(response, f"Table {self.table2.number}")
        self.assertContains(response, f"Capacity: {self.table2.capacity} guests")


    def test_check_availability_POST_no_tables_found(self):
        """
        Test no tables found for criteria.
        """
        # Book both tables
        Booking.objects.create(
            user=self.user, table=self.table1,
            booking_date=self.future_date, booking_time=self.booking_time, number_of_guests=2, status='confirmed'
        )
        Booking.objects.create(
            user=self.user, table=self.table2,
            booking_date=self.future_date, booking_time=self.booking_time, number_of_guests=4, status='confirmed'
        )
        form_data = {
            'check_date': self.future_date.isoformat(),
            'check_time': self.booking_time.strftime('%H:%M'),
            'num_guests': 3,
        }
        response = self.client.post(reverse('check_availability'), form_data)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'bookings/check_availability.html')
        self.assertIn('available_tables', response.context)
        self.assertEqual(len(response.context['available_tables']), 0)
        self.assertContains(
            response,
            "No tables available for the selected criteria. Please try a different date, time, or number of guests."
        )


    def test_check_availability_POST_invalid_form(self):
        """
        Test availability check with invalid form data (e.g., past date).
        """
        past_date = date.today() - timedelta(days=1)
        form_data = {
            'check_date': past_date.isoformat(),
            'check_time': '12:00',
            'num_guests': 2,
        }
        response = self.client.post(reverse('check_availability'), form_data)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'bookings/check_availability.html')
        self.assertFalse(response.context['form'].is_valid())
        self.assertContains(response, "You cannot check availability for a past date and time.")
