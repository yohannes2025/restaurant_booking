# bookings/tests/test_staff_views.py
from django.contrib.auth.models import User
from bookings.models import Table
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from datetime import date, time, timedelta, datetime
from django.utils import timezone
from bookings.models import Table, Booking
from bookings.models import Table

User = get_user_model()


def generate_unique_username(base='testuser'):
    return f"{base}_{uuid.uuid4().hex[:8]}"


class StaffViewsTest(TestCase):
    """
    Tests for staff-only views.
    """
    @classmethod
    @classmethod
    def setUpTestData(cls):
        cls.staff_user = User.objects.create_user(
            username='staffuser', password='password123', is_staff=True)
        cls.normal_user = User.objects.create_user(
            username='normaluser', password='password123')
        cls.table1 = Table.objects.create(number=10, capacity=4)
        cls.table2 = Table.objects.create(number=11, capacity=6)
        cls.today = timezone.now().date()
        cls.tomorrow = cls.today + timedelta(days=1)
        cls.yesterday = cls.today - timedelta(days=1)

        # Create some bookings for testing staff views
        cls.booking_today_pending = Booking.objects.create(
            user=cls.normal_user, table=cls.table1,  # THIS IS THE KEY BOOKING FOR TABLE1
            booking_date=cls.today, booking_time=time(14, 0), number_of_guests=2, status='pending'
        )
        cls.booking_tomorrow_confirmed = Booking.objects.create(
            user=cls.normal_user, table=cls.table2,
            booking_date=cls.tomorrow, booking_time=time(19, 0), number_of_guests=4, status='confirmed'
        )
        cls.booking_yesterday_completed = Booking.objects.create(
            # Another booking on table1 (past, completed)
            user=cls.normal_user, table=cls.table1,
            booking_date=cls.yesterday, booking_time=time(12, 0), number_of_guests=2, status='completed'
        )
        cls.booking_future_cancelled = Booking.objects.create(
            # Another booking on table1 (future, cancelled)
            user=cls.normal_user, table=cls.table1,
            booking_date=cls.today + timedelta(days=5), booking_time=time(10, 0), number_of_guests=2, status='cancelled'
        )

    def setUp(self):
        # This setup is fine as it creates a fresh login for each test
        self.client = Client()
        self.staff_user_for_login = User.objects.create_user(  # Give it a different name to avoid confusion
            username='teststaffuser',  # Ensure this username is truly unique
            password='testpassword',
            is_staff=True
        )
        login_successful = self.client.login(
            username='teststaffuser',
            password='testpassword'
        )
        self.assertTrue(login_successful, "Login failed in setUp.")

        # This `self.table` is only used by `test_staff_table_edit_POST_success`
        # and doesn't interfere with `cls.table1` or `cls.table2`
        self.table = Table.objects.create(number=100, capacity=4)

    # def setUp(self):
    #     self.client = Client()
    
    def setUp(self):
        # Create a staff user and log in
        self.staff_user = User.objects.create_user(
            username='teststaff',
            password='testpassword',
            is_staff=True
        )
        login_successful = self.client.login(
            username='teststaff',
            password='testpassword'
        )
        self.assertTrue(login_successful, "Login failed in setUp.")

        # Create a table with a unique number to avoid conflicts
        self.table = Table.objects.create(number=100, capacity=4)

    def test_staff_table_edit_POST_success(self):
        response = self.client.post(
            reverse('staff_table_edit', args=[self.table1.pk]),
            data={'number': 99, 'capacity': 6}
        )
        self.assertRedirects(response, reverse('staff_table_list'))

        self.table1.refresh_from_db()
        self.assertEqual(self.table1.number, 99)
        self.assertEqual(self.table1.capacity, 6)


    def test_staff_dashboard_access(self):
        """
        Test access to staff dashboard for staff and non-staff users.
        """
        # Staff user access
        self.client.login(username='staffuser', password='password123')
        response = self.client.get(reverse('staff_dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'bookings/staff_dashboard.html')
        self.assertIn('upcoming_active_bookings_count', response.context)
        self.assertIn('confirmed_today_count', response.context)
        self.assertIn('total_tables', response.context)

        # Non-staff user access (should be denied/redirected)
        self.client.logout()
        self.client.login(username='normaluser', password='password123')
        response = self.client.get(reverse('staff_dashboard'))
        # Redirect to login or permission denied
        self.assertEqual(response.status_code, 302)
        # The default behavior for staff_member_required is redirect to login if not authenticated
        # and then 403 Forbidden if authenticated but not staff. Django's test client follows redirects.
        # So it will redirect to login page, then potentially a 403 on that page if you check.
        # Simpler check: it won't be 200 and won't render the dashboard template.
        self.assertNotEqual(response.status_code, 200)

        # Unauthenticated user access
        self.client.logout()
        response = self.client.get(reverse('staff_dashboard'))
        self.assertEqual(response.status_code, 302)  # Redirect to login

    def test_staff_dashboard_counts(self):
        """
        Test the counts displayed on the staff dashboard.
        """
        self.client.login(username='staffuser', password='password123')
        response = self.client.get(reverse('staff_dashboard'))
        self.assertEqual(response.status_code, 200)

        # upcoming_active_bookings_count: pending today, confirmed tomorrow
        self.assertEqual(response.context['upcoming_active_bookings_count'], 2)

        # confirmed_today_count: only bookings confirmed today (if any)
        # Based on your data, only 'booking_tomorrow_confirmed' is confirmed tomorrow, so 0 for today
        self.assertEqual(response.context['confirmed_today_count'], 0)

        # Total tables
        self.assertEqual(
            response.context['total_tables'], Table.objects.count())


    def test_staff_booking_list_access(self):
        """
        Test access to staff booking list for staff and non-staff.
        """
        self.client.login(username='staffuser', password='password123')
        response = self.client.get(reverse('staff_booking_list'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'bookings/staff_booking_list.html')
        self.assertIn('bookings', response.context)
        self.assertEqual(
            response.context['bookings'].paginator.count, Booking.objects.count())

        self.client.logout()
        self.client.login(username='normaluser', password='password123')
        response = self.client.get(reverse('staff_booking_list'))
        # Redirect due to @staff_member_required
        self.assertEqual(response.status_code, 302)

    def test_staff_booking_list_search_and_filters(self):
        """
        Test search and filter functionality on staff booking list.
        """
        self.client.login(username='staffuser', password='password123')

        # Search by username
        response = self.client.get(
            reverse('staff_booking_list'), {'q': 'normaluser'})
        # All bookings are by normaluser
        self.assertEqual(len(response.context['bookings']), 4)

        # Filter by status
        response = self.client.get(reverse('staff_booking_list'), {
                                   'status': 'confirmed'})
        self.assertEqual(len(response.context['bookings']), 1)
        self.assertEqual(
            response.context['bookings'][0], self.booking_tomorrow_confirmed)

        # Filter by date
        response = self.client.get(reverse('staff_booking_list'), {
                                   'date': self.today.isoformat()})
        self.assertEqual(len(response.context['bookings']), 1)
        self.assertEqual(
            response.context['bookings'][0], self.booking_today_pending)

        # Combined filters (tomorrow's confirmed booking)
        response = self.client.get(reverse('staff_booking_list'), {
            'q': 'normaluser',
            'status': 'confirmed',
            'date': self.tomorrow.isoformat()
        })
        self.assertEqual(len(response.context['bookings']), 1)
        self.assertEqual(
            response.context['bookings'][0], self.booking_tomorrow_confirmed)

        # Invalid date format
        response = self.client.get(reverse('staff_booking_list'), {
                                   'date': '2024-02-30'})  # Invalid date
        self.assertEqual(response.status_code, 200)  # Still renders page
        messages = list(response.context['messages'])
        self.assertEqual(len(messages), 1)
        self.assertEqual(
            str(messages[0]), "Invalid date format. Please use YYYY-MM-DD.")
        # date_filter should be reset
        self.assertFalse(response.context['date_filter'])

    def test_staff_booking_detail_GET(self):
        """
        Test GET request to staff booking detail view.
        """
        self.client.login(username='staffuser', password='password123')
        response = self.client.get(reverse('staff_booking_detail', args=[
                                   self.booking_today_pending.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'bookings/staff_booking_detail.html')
        self.assertIn('booking', response.context)
        self.assertEqual(
            response.context['booking'], self.booking_today_pending)
        self.assertIn('form', response.context)  # Form for status update

    def test_staff_booking_detail_POST_update_status(self):
        """
        Test updating booking status from staff detail view.
        """
        self.client.login(username='staffuser', password='password123')
        initial_status = self.booking_today_pending.status
        form_data = {
            'status': 'confirmed',
            'notes': 'Confirmed by staff.'
        }
        response = self.client.post(
            reverse('staff_booking_detail', args=[
                    self.booking_today_pending.pk]),
            data=form_data,
            follow=True  # Follow redirect to get final response
        )
        self.assertEqual(response.status_code, 200)
        self.assertRedirects(response, reverse('staff_booking_list'))
        self.booking_today_pending.refresh_from_db()
        self.assertEqual(self.booking_today_pending.status, 'confirmed')
        self.assertEqual(self.booking_today_pending.notes,
                         'Confirmed by staff.')
        self.assertContains(
            response, "Booking status updated successfully!", html=False)

    def test_staff_table_list_access(self):
        """
        Test access to staff table list for staff and non-staff.
        """
        self.client.login(username='staffuser', password='password123')
        response = self.client.get(reverse('staff_table_list'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'bookings/staff_table_list.html')
        self.assertIn('tables', response.context)
        self.assertEqual(
            len(response.context['tables']), Table.objects.count())
        self.assertIn('form', response.context)  # Form for adding new tables

        self.client.logout()
        self.client.login(username='normaluser', password='password123')
        response = self.client.get(reverse('staff_table_list'))
        # Redirect due to @staff_member_required
        self.assertEqual(response.status_code, 302)

        def test_staff_table_list_POST_add_table(self):
            """
            Test POST request to add a new table from the staff table list view.
            """
            self.client.login(username='staffuser', password='password123')

            # Data for the new table with a unique number (e.g., 101)
            new_table_number = 101
            response = self.client.post(reverse('staff_table_list'), {
                'number': new_table_number,
                'capacity': 6
            }, follow=True)

            # Check that the response contains the success message
            self.assertContains(
                response, f"Table {new_table_number} added successfully!")

            # Verify that the new table exists in the database
            self.assertTrue(Table.objects.filter(number=new_table_number).exists())

    def test_staff_table_list_POST_add_table_duplicate_number(self):
        """
        Test adding a table with a duplicate number.
        """
        self.client.login(username='staffuser', password='password123')

        response = self.client.post(reverse('staff_table_list'), {
            'number': self.table1.number,  # duplicate number
            'capacity': 5
        }, follow=True)

        self.assertEqual(response.status_code, 200)

        # Assert the specific field error message (this is good to keep)
        self.assertContains(
            response, "Table with this Table Number already exists.")

        # Assert the message you *are* sending via messages.error()
        # You need to make sure this matches exactly what's in your views.py
        self.assertContains(
            response, "Please correct the errors in the form when adding a table.")

        # Ensure no new Table object was created
        # Assuming you start with 3 tables
        self.assertEqual(Table.objects.count(), 3)


    def test_staff_table_edit_GET(self):
        """
        Test GET request to staff table edit view.
        """
        self.client.login(username='staffuser', password='password123')
        response = self.client.get(
            reverse('staff_table_edit', args=[self.table1.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'bookings/staff_table_edit.html')
        self.assertIn('form', response.context)
        self.assertEqual(response.context['table'], self.table1)
        self.assertEqual(response.context['form'].instance, self.table1)

    # def generate_unique_username(self, base='staffuser'):
    #     """Generate a unique username."""
    #     return f"{base}_{uuid.uuid4().hex[:8]}"


    def test_staff_table_delete_POST_success(self):
        # Create a new table with a unique number
        table_to_delete = Table.objects.create(number=200, capacity=4)

        initial_table_count = Table.objects.count()

        # Send POST request to delete the table
        response = self.client.post(
            reverse('staff_table_delete', args=[table_to_delete.pk])
        )

        # Assert redirect
        self.assertEqual(response.status_code, 302)

        # Check if the table is deleted
        exists_after_delete = Table.objects.filter(
            pk=table_to_delete.pk).exists()
        self.assertFalse(exists_after_delete,
                         "Table still exists after delete.")

        # Check count decreased
        post_delete_count = Table.objects.count()
        self.assertEqual(
            post_delete_count,
            initial_table_count - 1,
            f"Expected {initial_table_count - 1} tables, found {post_delete_count}"
        )

    def test_staff_table_delete_POST_with_active_bookings(self):
        # Ensure staff user is logged in
        self.client.login(username='teststaffuser', password='testpassword')

        # --- CRITICAL: Create a fresh booking for table1 within this test ---
        # This ensures the booking exists ONLY for this test run and isn't affected by others.
        # Use cls.normal_user as the user for the booking
        active_booking_for_table1 = Booking.objects.create(
            user=self.normal_user,  # Use cls.normal_user from setUpTestData
            table=self.table1,     # Use cls.table1 from setUpTestData
            booking_date=timezone.now().date() + timedelta(days=10),  # Definitely in the future
            booking_time=time(18, 0),
            number_of_guests=3,
            status='confirmed'  # A clear 'active' status
        )
        print(
            f"DEBUG TEST: Created booking {active_booking_for_table1.pk} for table {self.table1.pk}")
        print(
            f"DEBUG TEST: Table {self.table1.pk} has {self.table1.bookings.count()} related bookings.")

        initial_table_count = Table.objects.count()

        # The table we want to delete is cls.table1
        url = reverse('staff_table_delete', args=[self.table1.pk])
        response = self.client.post(url)

        # Assert that the response status code is 200 (OK)
        # because the view should re-render the page with an error, not redirect.
        self.assertEqual(response.status_code, 200)

        # Assert that the table still exists in the database
        self.assertEqual(Table.objects.count(), initial_table_count)
        self.assertTrue(Table.objects.filter(pk=self.table1.pk).exists())

        # Assert that the error message is displayed
        messages = list(response.context['messages'])
        self.assertEqual(len(messages), 1)
        self.assertIn(
            "This table cannot be deleted as it has active bookings.", str(messages[0]))

        # Assert that the correct template was rendered
        self.assertTemplateUsed(response, 'bookings/staff_table_list.html')

        # Clean up the specific booking created by this test (optional, but good for clarity)
        active_booking_for_table1.delete()
