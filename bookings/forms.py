# bookings/forms.py
from django import forms
from .models import Booking
from datetime import date, time


class BookingForm(forms.ModelForm):
    booking_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date', 'min': date.today().isoformat()}),
                                   initial=date.today())
    booking_time = forms.TimeField(
        widget=forms.TimeInput(attrs={'type': 'time'}))

    class Meta:
        model = Booking
        fields = ['booking_date', 'booking_time', 'number_of_guests', 'notes']
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 4}),
        }

    def clean(self):
        cleaned_data = super().clean()
        booking_date = cleaned_data.get('booking_date')
        booking_time = cleaned_data.get('booking_time')
        number_of_guests = cleaned_data.get('number_of_guests')

        # Basic validation for future dates and valid time
        if booking_date and booking_date < date.today():
            self.add_error(
                'booking_date', "Booking date cannot be in the past.")

        # You might want more sophisticated time validation (e.g., restaurant opening hours)
        # For example, ensure time is within 9 AM to 10 PM
        if booking_time:
            if not (time(9, 0) <= booking_time <= time(22, 0)):
                self.add_error(
                    'booking_time', "Booking time must be between 9:00 AM and 10:00 PM.")

        if number_of_guests and number_of_guests <= 0:
            self.add_error('number_of_guests',
                           "Number of guests must be at least 1.")

        return cleaned_data
