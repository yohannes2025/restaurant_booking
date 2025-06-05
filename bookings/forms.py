# bookings/forms.py
from .models import Table, Booking
from django import forms
from django.utils import timezone
from datetime import date, time, datetime, timedelta
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django.contrib.auth.models import User


class CustomUserCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        # You can add 'email' here if you want it on your registration form.
        # If adding email, consider making it unique in your User model if not already handled.
        fields = UserCreationForm.Meta.fields + ('email',)

        
class BookingForm(forms.ModelForm):
    booking_date = forms.DateField(
        widget=forms.DateInput(
            attrs={'type': 'date', 'min': date.today().isoformat(), 'class': 'form-control'}),
        initial=date.today()
    )
    booking_time = forms.TimeField(
        widget=forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'})
    )
    number_of_guests = forms.IntegerField(
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 1})
    )

    class Meta:
        model = Booking
        fields = ['booking_date', 'booking_time', 'number_of_guests', 'notes']
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
        }
        labels = {
            'booking_date': 'Preferred Date',
            'booking_time': 'Preferred Time',
            'number_of_guests': 'Number of Guests',
            'notes': 'Special Requests/Notes',
        }


class AvailabilityForm(forms.Form):
    check_date = forms.DateField(
        label='Date',
        widget=forms.DateInput(
            attrs={'type': 'date', 'min': date.today().isoformat(), 'class': 'form-control'}),
        initial=date.today()
    )
    check_time = forms.TimeField(
        label='Time',
        widget=forms.TimeInput(
            attrs={'type': 'time', 'class': 'form-control'}),
        initial=time(19, 0)  # Default to 7 PM
    )
    num_guests = forms.IntegerField(
        label='Number of Guests',
        min_value=1,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
        initial=2
    )

    def clean(self):
        cleaned_data = super().clean()
        check_date = cleaned_data.get('check_date')
        check_time = cleaned_data.get('check_time')

        if check_date and check_time:
            # Combine naive datetime
            check_datetime = datetime.combine(check_date, check_time)
            # Make aware datetime with current timezone
            check_datetime = timezone.make_aware(
                check_datetime, timezone.get_current_timezone())

            if check_datetime < timezone.now() - timedelta(minutes=1):  # Allow current minute
                raise forms.ValidationError(
                    "You cannot check availability for a past date and time.")

            # Restaurant hours validation
            if not (time(9, 0) <= check_time <= time(22, 0)):
                raise forms.ValidationError(
                    "Restaurant is open from 9:00 AM to 10:00 PM.")

        return cleaned_data


class BookingStatusUpdateForm(forms.ModelForm):
    class Meta:
        model = Booking
        fields = ['status', 'notes']  # Staff can update status and notes
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
        }
        labels = {
            'status': 'Booking Status',
        }


class TableForm(forms.ModelForm):
    class Meta:
        model = Table
        # Adjust fields to match your Table model
        fields = ['number', 'capacity']


# from django import forms

# from .models import Booking
# import datetime
# from django.utils import timezone
# from datetime import date, time, datetime, timedelta



# class BookingForm(forms.ModelForm):
#     booking_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date', 'min': date.today().isoformat(), 'class': 'form-control'}),
#                                    initial=date.today())
#     booking_time = forms.TimeField(widget=forms.TimeInput(
#         attrs={'type': 'time', 'class': 'form-control'}))
#     number_of_guests = forms.IntegerField(
#         widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 1}))

#     class Meta:
#         model = Booking
#         fields = ['booking_date', 'booking_time', 'number_of_guests', 'notes']
#         widgets = {
#             'notes': forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
#         }
#         labels = {
#             'booking_date': 'Preferred Date',
#             'booking_time': 'Preferred Time',
#             'number_of_guests': 'Number of Guests',
#             'notes': 'Special Requests/Notes',
#         }

# # New form for availability check


# class AvailabilityForm(forms.Form):
#     check_date = forms.DateField(
#         label='Date',
#         widget=forms.DateInput(
#             attrs={'type': 'date', 'min': date.today().isoformat(), 'class': 'form-control'}),
#         initial=date.today()
#     )
#     check_time = forms.TimeField(
#         label='Time',
#         widget=forms.TimeInput(
#             attrs={'type': 'time', 'class': 'form-control'}),
#         initial=time(19, 0)  # Default to 7 PM
#     )
#     num_guests = forms.IntegerField(
#         label='Number of Guests',
#         min_value=1,
#         widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
#         initial=2
#     )

#     def clean(self):
#         cleaned_data = super().clean()
#         check_date = cleaned_data.get('check_date')
#         check_time = cleaned_data.get('check_time')

#         if check_date and check_time:
#             check_datetime = datetime.combine(check_date, check_time)
#             if check_datetime < timezone.now() - timedelta(minutes=1):  # Allow current minute
#                 raise forms.ValidationError(
#                     "You cannot check availability for a past date and time.")

#             # Add more specific time validation (e.g., restaurant hours)
#             if not (time(9, 0) <= check_time <= time(22, 0)):
#                 raise forms.ValidationError(
#                     "Restaurant is open from 9:00 AM to 10:00 PM.")

#         return cleaned_data

# class BookingStatusUpdateForm(forms.ModelForm):
#     class Meta:
#         model = Booking
#         fields = ['status', 'notes']  # Staff can update status and notes
#         widgets = {
#             'notes': forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
#             'status': forms.Select(attrs={'class': 'form-select'}),
#         }
#     labels = {
#         'status': 'Booking Status',
#     }


# # bookings/forms.py
# from django import forms
# from .models import Booking
# from datetime import date, time


# class BookingForm(forms.ModelForm):
#     booking_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date', 'min': date.today().isoformat()}),
#                                    initial=date.today())
#     booking_time = forms.TimeField(
#         widget=forms.TimeInput(attrs={'type': 'time'}))

#     class Meta:
#         model = Booking
#         fields = ['booking_date', 'booking_time', 'number_of_guests', 'notes']
#         widgets = {
#             'notes': forms.Textarea(attrs={'rows': 4}),
#         }

#     def clean(self):
#         cleaned_data = super().clean()
#         booking_date = cleaned_data.get('booking_date')
#         booking_time = cleaned_data.get('booking_time')
#         number_of_guests = cleaned_data.get('number_of_guests')

#         # Basic validation for future dates and valid time
#         if booking_date and booking_date < date.today():
#             self.add_error(
#                 'booking_date', "Booking date cannot be in the past.")

#         # You might want more sophisticated time validation (e.g., restaurant opening hours)
#         # For example, ensure time is within 9 AM to 10 PM
#         if booking_time:
#             if not (time(9, 0) <= booking_time <= time(22, 0)):
#                 self.add_error(
#                     'booking_time', "Booking time must be between 9:00 AM and 10:00 PM.")

#         if number_of_guests and number_of_guests <= 0:
#             self.add_error('number_of_guests',
#                            "Number of guests must be at least 1.")

#         return cleaned_data


# bookings/forms.py
