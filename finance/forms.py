from django import forms
from accounts.models import Campus
from students.models import Student
from .models import FeeAssignment


class FeeAssignmentForm(forms.Form):
    assignment_type = forms.ChoiceField(choices=FeeAssignment.AssignmentType.choices)
    campus = forms.ModelChoiceField(queryset=Campus.objects.none())
    programme = forms.CharField(required=False, max_length=150)
    year_of_study = forms.IntegerField(required=False, min_value=1, max_value=10)
    student = forms.ModelChoiceField(queryset=Student.objects.none(), required=False)
    academic_year = forms.CharField(max_length=20)
    semester = forms.ChoiceField(choices=FeeAssignment.Semester.choices)
    amount = forms.DecimalField(max_digits=12, decimal_places=2, min_value=0.01)
    description = forms.CharField(max_length=255)

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        campuses = Campus.objects.filter(is_active=True)
        if user and not (user.is_superuser or getattr(user, "is_central_admin", False)):
            campuses = campuses.filter(pk=user.campus_id)
        self.fields["campus"].queryset = campuses
        students = Student.objects.filter(status="ACTIVE").select_related("campus", "user")
        if user and not (user.is_superuser or getattr(user, "is_central_admin", False)):
            students = students.filter(campus_id=user.campus_id)
        self.fields["student"].queryset = students
