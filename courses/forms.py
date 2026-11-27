from django import forms
from accounts.models import Campus, User
from .models import Course


class CourseForm(forms.ModelForm):

    class Meta:
        model = Course
        fields = [
            "course_code",
            "course_title",
            "description",
            "campus",
            "programme",
            "year_of_study",
            "semester",
            "credit_units",
            "department",
            "academic_year",
            "lecturer",
            "is_active",
        ]

        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "year_of_study": forms.Select(choices=[
                (1, "Year 1"),
                (2, "Year 2"),
            ]),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

        central = bool(
            self.user and (
                self.user.is_superuser or self.user.is_central_admin
            )
        )

        if central:
            self.fields["campus"].queryset = Campus.objects.filter(
                is_active=True
            ).order_by("name")
            self.fields["campus"].required = True
            self.fields["campus"].empty_label = "Select campus"
        else:
            campus_id = getattr(self.user, "campus_id", None)

            self.fields["campus"].queryset = Campus.objects.filter(
                pk=campus_id
            )
            self.fields["campus"].initial = campus_id
            self.fields["campus"].widget = forms.HiddenInput()
            self.fields["campus"].required = True

        lecturer_queryset = User.objects.filter(
            role="LECTURER",
            is_active=True
        )

        if not central:
            lecturer_queryset = lecturer_queryset.filter(
                campus_id=getattr(self.user, "campus_id", None)
            )

        self.fields["lecturer"].queryset = lecturer_queryset.order_by(
            "username"
        )
        self.fields["lecturer"].required = False

    def clean(self):
        cleaned_data = super().clean()
        campus = cleaned_data.get("campus")
        lecturer = cleaned_data.get("lecturer")

        if lecturer and campus and lecturer.campus_id != campus.id:
            self.add_error(
                "lecturer",
                "The selected lecturer must belong to the course campus."
            )

        if lecturer and not campus:
            self.add_error(
                "campus",
                "Select a campus before assigning a lecturer."
            )

        return cleaned_data
