from django import forms
from courses.models import Course
from .models import LiveClassroom


class LiveClassroomForm(forms.ModelForm):

    class Meta:
        model = LiveClassroom
        fields = [
            "course",
            "title",
            "description",
            "start_time",
            "end_time",
            "zoom_link",
        ]
        widgets = {
            "course": forms.Select(attrs={"class": "form-control"}),
            "title": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Enter classroom topic"
            }),
            "description": forms.Textarea(attrs={
                "class": "form-control",
                "rows": 4
            }),
            "start_time": forms.DateTimeInput(
                attrs={
                    "class": "form-control",
                    "type": "datetime-local"
                },
                format="%Y-%m-%dT%H:%M"
            ),
            "end_time": forms.DateTimeInput(
                attrs={
                    "class": "form-control",
                    "type": "datetime-local"
                },
                format="%Y-%m-%dT%H:%M"
            ),
            "zoom_link": forms.URLInput(attrs={
                "class": "form-control",
                "placeholder": "https://zoom.us/j/..."
            }),
        }
        input_formats = ["%Y-%m-%dT%H:%M"]

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)

        courses = Course.objects.filter(
            is_active=True,
            lecturer__isnull=False,
            lecturer__is_active=True
        )

        if user is not None and not (user.is_central_admin or user.is_superuser):
            if user.campus_id is None:
                courses = courses.none()
            else:
                courses = courses.filter(
                    lecturer__campus_id=user.campus_id
                )

        self.fields["course"].queryset = courses.order_by("course_code")

