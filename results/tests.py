from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from accounts.models import Campus
from courses.models import Course, CourseEnrollment
from students.models import Student
from .models import StudentResult, ResultAuditLog

User = get_user_model()


class ResultsSecurityTests(TestCase):

    def setUp(self):
        self.namugongo = Campus.objects.create(
            code="TEST-NAM", name="Test Namugongo",
            phone_primary="0700000001", phone_secondary="0700000002",
            is_command_centre=True,
        )
        self.busia = Campus.objects.create(
            code="TEST-BUS", name="Test Busia",
            phone_primary="0700000003", phone_secondary="0700000004",
        )

        self.lecturer = User.objects.create_user(
            username="testlecturer", password="TestPassword123!",
            role=User.Roles.LECTURER, campus=self.namugongo,
        )
        self.other_lecturer = User.objects.create_user(
            username="otherlecturer", password="TestPassword123!",
            role=User.Roles.LECTURER, campus=self.busia,
        )
        self.campus_admin = User.objects.create_user(
            username="testcampusadmin", password="TestPassword123!",
            role=User.Roles.ADMINISTRATOR, campus=self.namugongo,
        )
        self.central_admin = User.objects.create_user(
            username="testcentraladmin", password="TestPassword123!",
            role=User.Roles.ADMINISTRATOR, campus=self.namugongo,
            is_central_admin=True,
        )

        self.student_user = User.objects.create_user(
            username="teststudent", password="TestPassword123!",
            role=User.Roles.STUDENT, campus=self.namugongo,
        )
        self.other_student_user = User.objects.create_user(
            username="otherstudent", password="TestPassword123!",
            role=User.Roles.STUDENT, campus=self.namugongo,
        )

        self.student = Student.objects.create(
            user=self.student_user, campus=self.namugongo,
            registration_number="TEST/001",
            gender=Student.Gender.MALE,
            programme="Diploma in Education",
        )
        self.other_student = Student.objects.create(
            user=self.other_student_user, campus=self.busia,
            registration_number="TEST/002",
            gender=Student.Gender.FEMALE,
            programme="Diploma in Education",
        )

        self.course = Course.objects.create(
            course_code="TEST101", course_title="Test Course",
            campus=self.namugongo, lecturer=self.lecturer,
            programme="Diploma in Education", academic_year="2026",
        )
        self.other_course = Course.objects.create(
            course_code="TEST201", course_title="Busia Test Course",
            campus=self.busia, lecturer=self.other_lecturer,
            programme="Diploma in Education", academic_year="2026",
        )

        CourseEnrollment.objects.create(
            student=self.student, course=self.course,
        )
        CourseEnrollment.objects.create(
            student=self.other_student, course=self.course,
        )

    def make_result(
        self, student=None, course=None,
        status=StudentResult.Status.DRAFT,
        coursework=Decimal("30"),
        examination=Decimal("45"),
        published=False,
    ):
        return StudentResult.objects.create(
            student=student or self.student,
            course=course or self.course,
            academic_year="2026",
            semester="SEMESTER 1",
            coursework_marks=coursework,
            examination_marks=examination,
            status=status,
            is_published=published,
        )

    def test_lecturer_can_open_assigned_course(self):
        self.client.force_login(self.lecturer)
        response = self.client.get(reverse(
            "results:course_marks", kwargs={"course_id": self.course.id}
        ))
        self.assertEqual(response.status_code, 200)

    def test_lecturer_cannot_open_another_lecturers_course(self):
        self.client.force_login(self.lecturer)
        response = self.client.get(reverse(
            "results:course_marks",
            kwargs={"course_id": self.other_course.id},
        ))
        self.assertEqual(response.status_code, 404)

    def test_campus_admin_only_sees_own_campus_results(self):
        own_result = self.make_result(status=StudentResult.Status.SUBMITTED)
        other_result = self.make_result(
            student=self.other_student, course=self.other_course,
            status=StudentResult.Status.SUBMITTED,
        )

        self.client.force_login(self.campus_admin)
        response = self.client.get(reverse("results:review_results"))

        self.assertEqual(response.status_code, 200)
        visible = list(response.context["results"])
        self.assertIn(own_result, visible)
        self.assertNotIn(other_result, visible)

    def test_central_admin_can_see_both_campuses(self):
        own_result = self.make_result(status=StudentResult.Status.SUBMITTED)
        other_result = self.make_result(
            student=self.other_student, course=self.other_course,
            status=StudentResult.Status.SUBMITTED,
        )

        self.client.force_login(self.central_admin)
        response = self.client.get(reverse("results:review_results"))

        self.assertEqual(response.status_code, 200)
        visible = list(response.context["results"])
        self.assertIn(own_result, visible)
        self.assertIn(other_result, visible)

    def test_student_only_sees_own_published_results(self):
        own_result = self.make_result(
            status=StudentResult.Status.PUBLISHED, published=True,
        )
        self.make_result(
            student=self.other_student,
            status=StudentResult.Status.PUBLISHED, published=True,
        )


        self.client.force_login(self.student_user)
        response = self.client.get(reverse("results:student_results"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["results"]), [own_result])

    def test_draft_result_cannot_be_published(self):
        result = self.make_result()
        self.client.force_login(self.campus_admin)

        response = self.client.post(reverse(
            "results:publish_result", kwargs={"result_id": result.id}
        ))

        self.assertEqual(response.status_code, 404)
        result.refresh_from_db()
        self.assertFalse(result.is_published)

    def test_approved_result_can_be_published_and_audited(self):
        result = self.make_result(status=StudentResult.Status.APPROVED)
        self.client.force_login(self.campus_admin)

        response = self.client.post(reverse(
            "results:publish_result", kwargs={"result_id": result.id}
        ))

        self.assertEqual(response.status_code, 302)
        result.refresh_from_db()

        self.assertTrue(result.is_published)
        self.assertEqual(result.status, StudentResult.Status.PUBLISHED)
        self.assertEqual(result.published_by, self.campus_admin)
        self.assertTrue(ResultAuditLog.objects.filter(
            result=result, actor=self.campus_admin,
            action=ResultAuditLog.Action.PUBLISHED,
        ).exists())

    def test_lecturer_submission_returns_to_course_marks(self):

        self.make_result(student=self.student)
        self.make_result(student=self.other_student)

        self.client.force_login(self.lecturer)
        response = self.client.post(
            reverse(
                "results:submit_course_results",
                kwargs={"course_id": self.course.id},
            ),
            {"academic_year": "2026"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn(f"/results/course/{self.course.id}/", response.url)
        self.assertIn("academic_year=2026", response.url)

        self.assertEqual(StudentResult.objects.filter(
            course=self.course,
            status=StudentResult.Status.SUBMITTED,
        ).count(), 2)

        self.assertEqual(ResultAuditLog.objects.filter(
            action=ResultAuditLog.Action.SUBMITTED,
            actor=self.lecturer,
        ).count(), 2)

    def test_coursework_cannot_exceed_40(self):
        result = StudentResult(
            student=self.student, course=self.course,
            academic_year="2026", semester="SEMESTER 1",
            coursework_marks=Decimal("41"),
            examination_marks=Decimal("45"),
        )
        with self.assertRaises(ValidationError):
            result.full_clean()

    def test_examination_cannot_exceed_60(self):
        result = StudentResult(
            student=self.student, course=self.course,
            academic_year="2026", semester="SEMESTER 1",
            coursework_marks=Decimal("30"),
            examination_marks=Decimal("61"),
        )
        with self.assertRaises(ValidationError):
            result.full_clean()

    def test_valid_marks_total_100(self):
        result = self.make_result(
            coursework=Decimal("40"), examination=Decimal("60"),
        )
        self.assertEqual(result.total_marks, Decimal("100"))



