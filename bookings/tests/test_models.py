# bookings/tests/test_models.py
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.db.utils import IntegrityError
from datetime import date, time, timedelta
from bookings.models import Table, Booking

User = get_user_model()


class TableModelTest(TestCase):
    """
    Tests for the Table model.
    """

    def test_create_table(self):
        """
        Test that a Table object can be created successfully with correct attributes.
        """
        table = Table.objects.create(number=1, capacity=4)
        self.assertEqual(table.number, 1)
        self.assertEqual(table.capacity, 4)
        self.assertEqual(str(table), "Table 1 (Capacity: 4)")

    def test_unique_table_number(self):
        """
        Test that table numbers must be unique.
        """
        Table.objects.create(number=10, capacity=4)
        with self.assertRaises(IntegrityError):
            # Should raise error due to unique=True
            Table.objects.create(number=10, capacity=6)

    def test_table_capacity_validation(self):
        """
        Test that capacity cannot be negative (though model field doesn't enforce this directly,
        it's a good practice to consider; forms should handle this primarily).
        """
        # Model field doesn't explicitly prevent negative, but you might add clean method for it
        # For now, it will allow it but forms prevent it.
        # This will pass at model level
        table = Table.objects.create(number=2, capacity=-1)
        # This is expected behavior for now
        self.assertEqual(table.capacity, -1)
        # If you were to add a clean method to the model:
        # with self.assertRaises(ValidationError):
        #    table.full_clean()


class BookingModelTest(TestCase):
    """
    Tests for the Booking model.
    """
    @classmethod
    def setUpTestData(cls):
        """
        Set up non-modified objects for all test methods in this class.
        """
        cls.user = User.objects.create_user(
            username='testuser', password='password123')
        cls.table = Table.objects.create(number=5, capacity=4)
        cls.future_date = date.today() + timedelta(days=7)
        cls.booking_time = time(18, 0)  # 6 PM

    def test_create_booking(self):
        """
        Test that a Booking object can be created successfully with correct attributes.
        """
        booking = Booking.objects.create(
            user=self.user,
            table=self.table,
            booking_date=self.future_date,
            booking_time=self.booking_time,
            number_of_guests=2,
            notes="Birthday",
            status='pending'
        )
        self.assertEqual(booking.user, self.user)
        self.assertEqual(booking.table, self.table)
        self.assertEqual(booking.booking_date, self.future_date)
        self.assertEqual(booking.booking_time, self.booking_time)
        self.assertEqual(booking.number_of_guests, 2)
        self.assertEqual(booking.notes, "Birthday")
        self.assertEqual(booking.status, 'pending')
        self.assertTrue(booking.created_at)
        self.assertTrue(booking.updated_at)
        self.assertEqual(
            str(booking),
            f"Booking by {self.user.username} for Table {self.table.number} on {self.future_date} at {self.booking_time} (pending)"
        )

    def test_unique_together_constraint(self):
        """
        Test the unique_together constraint for (table, booking_date, booking_time).
        """
        Booking.objects.create(
            user=self.user,
            table=self.table,
            booking_date=self.future_date,
            booking_time=self.booking_time,
            number_of_guests=2,
            status='pending'
        )
        # Attempt to create another booking for the same table at the exact same date and time
        with self.assertRaises(IntegrityError):
            Booking.objects.create(
                user=self.user,
                table=self.table,
                booking_date=self.future_date,
                booking_time=self.booking_time,
                number_of_guests=3,  # Different guests, but same time/table
                status='pending'
            )

    def test_booking_status_choices(self):
        """
        Test that booking status choices are as expected.
        """
        expected_choices = [
            ('pending', 'Pending'),
            ('confirmed', 'Confirmed'),
            ('cancelled', 'Cancelled'),
            ('completed', 'Completed'),
        ]
        self.assertEqual(Booking.BOOKING_STATUS_CHOICES, expected_choices)

    def test_table_on_delete_protect(self):
        """
        Test that a Table cannot be deleted if it has associated Bookings.
        """
        Booking.objects.create(
            user=self.user,
            table=self.table,
            booking_date=self.future_date,
            booking_time=self.booking_time,
            number_of_guests=2,
            status='pending'
        )
        # ProtectedError is a subclass of IntegrityError
        with self.assertRaises(IntegrityError):
            self.table.delete()

    def test_user_on_delete_cascade(self):
        """
        Test that bookings are deleted when the associated user is deleted.
        """
        Booking.objects.create(
            user=self.user,
            table=self.table,
            booking_date=self.future_date,
            booking_time=self.booking_time,
            number_of_guests=2,
            status='pending'
        )
        self.assertEqual(Booking.objects.count(), 1)
        self.user.delete()
        self.assertEqual(Booking.objects.count(), 0)
