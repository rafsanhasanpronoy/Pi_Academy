from datetime import date, timedelta
from io import BytesIO

import openpyxl
from django.contrib import admin
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from .admin import ExamResultAdmin, StudentAdmin, _finance_summary
from .forms import AdmissionInquiryForm, ContactMessageForm, ExpenseForm, StudentLookupForm
from .models import (
    Attendance, Batch, Class, Exam, ExamResult, Expense, Faculty, Student,
    StudentPayment, StudentPaymentReceipt, Subject, TeacherSalary,
)


def _make_xlsx(headers, rows):
    """Builds an in-memory .xlsx matching what a real upload looks like,
    so these tests exercise the same openpyxl parsing path as a real
    file — not a shortcut that skips it."""
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.append(headers)
    for row in rows:
        sheet.append(row)
    buffer = BytesIO()
    workbook.save(buffer)
    buffer.seek(0)
    return buffer


class ContactMessageFormTests(TestCase):
    def test_rejects_when_no_phone_and_no_email(self):
        form = ContactMessageForm(data={
            "name": "Rafsan",
            "phone": "",
            "email": "",
            "message": "Hello",
        })
        self.assertFalse(form.is_valid())
        self.assertIn("__all__", form.errors)

    def test_valid_with_phone_only(self):
        form = ContactMessageForm(data={
            "name": "Rafsan",
            "phone": "01700000000",
            "email": "",
            "message": "Hello",
        })
        self.assertTrue(form.is_valid())

    def test_honeypot_rejects_bot_submission(self):
        form = ContactMessageForm(data={
            "name": "Bot",
            "phone": "01700000000",
            "email": "",
            "message": "spam",
            "website": "http://spam.example",  # a human never fills this in
        })
        self.assertFalse(form.is_valid())


class AdmissionInquiryFormTests(TestCase):
    def test_minimal_valid_submission(self):
        form = AdmissionInquiryForm(data={
            "student_name": "Test Student",
            "student_phone": "01700000000",
            "guardian_name": "",
            "guardian_phone": "",
            "class_obj": "",
            "message": "",
        })
        self.assertTrue(form.is_valid())

    def test_honeypot_rejects_bot_submission(self):
        form = AdmissionInquiryForm(data={
            "student_name": "Bot Student",
            "student_phone": "01700000000",
            "website": "http://spam.example",
        })
        self.assertFalse(form.is_valid())


class StudentResultsRateLimitTests(TestCase):
    """
    Covers the fix for the brute-force lookup risk flagged in QA: after
    the rate limit is hit, further POSTs must be blocked rather than
    silently allowed through.
    """

    def setUp(self):
        cache.clear()
        self.url = reverse("results")
        self.klass = Class.objects.create(class_name="Class 9", academic_year=2026)
        self.batch = Batch.objects.create(class_obj=self.klass, batch_name="Morning")
        self.student = Student.objects.create(
            student_code="STU-2026-001",
            class_obj=self.klass,
            batch=self.batch,
            full_name="Test Student",
            student_phone="01700000000",
        )

    @override_settings(RATELIMIT_ENABLE=True)
    def test_blocked_after_rate_limit_exceeded(self):
        payload = {"student_code": "WRONG-CODE", "student_phone": "0000000000"}
        responses = [self.client.post(self.url, payload) for _ in range(6)]
        # The 6th attempt within a minute from the same client should be
        # blocked (django-ratelimit raises Ratelimited -> 403 by default).
        self.assertEqual(responses[-1].status_code, 403)

    def test_correct_credentials_return_student_data(self):
        response = self.client.post(self.url, {
            "student_code": "STU-2026-001",
            "student_phone": "01700000000",
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test Student")

    def test_wrong_credentials_do_not_leak_which_field_was_wrong(self):
        response = self.client.post(self.url, {
            "student_code": "STU-2026-001",
            "student_phone": "09999999999",
        })
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Test Student")


class DashboardOrderingTests(TestCase):
    """Achievements with no date shouldn't unpredictably jump to the top."""

    def test_null_dates_sort_last(self):
        from .models import Achievement

        Achievement.objects.create(title="Dated", is_published=True, achievement_date="2026-01-01")
        Achievement.objects.create(title="Undated", is_published=True, achievement_date=None)

        response = self.client.get(reverse("achievements"))
        content = response.content.decode()
        self.assertLess(content.index("Dated"), content.index("Undated"))


class StudentBulkUploadTests(TestCase):
    """
    Covers StudentAdmin._process_bulk_upload — the spreadsheet-parsing
    path flagged in QA as the highest silent-failure risk in the admin,
    since a malformed row can otherwise fail quietly with nothing to
    catch it.
    """

    HEADERS = [
        "Full Name", "Class Name", "Academic Year", "Batch Name", "Gender",
        "Date of Birth (YYYY-MM-DD)", "Student Phone", "Father's Name",
        "Father's Phone", "Mother's Name", "Mother's Phone", "Address",
        "Admission Date (YYYY-MM-DD)", "Status",
    ]

    def setUp(self):
        self.admin = StudentAdmin(Student, admin.site)
        self.klass = Class.objects.create(class_name="Class 6", academic_year=2026)
        self.batch = Batch.objects.create(class_obj=self.klass, batch_name="Morning")

    def test_valid_row_creates_student_with_generated_code(self):
        upload = _make_xlsx(self.HEADERS, [[
            "Jane Doe", "Class 6", 2026, "Morning", "Female",
            "2014-05-12", "01700000000", "John Doe", "01700000001",
            "Mary Doe", "01700000002", "House 12, Road 4", "2026-01-10", "Active",
        ]])
        result = self.admin._process_bulk_upload(upload)
        self.assertEqual(result["created_count"], 1)
        self.assertEqual(result["errors"], [])
        student = Student.objects.get(full_name="Jane Doe")
        self.assertTrue(student.student_code.startswith("PiC6"))

    def test_missing_full_name_is_skipped_with_error_not_silently(self):
        upload = _make_xlsx(self.HEADERS, [[
            "", "Class 6", 2026, "Morning", "Female",
            "2014-05-12", "01700000000", "", "", "", "", "", "", "Active",
        ]])
        result = self.admin._process_bulk_upload(upload)
        self.assertEqual(result["created_count"], 0)
        self.assertEqual(Student.objects.count(), 0)
        self.assertTrue(any("missing Full Name" in e for e in result["errors"]))

    def test_unknown_class_is_skipped_with_error(self):
        upload = _make_xlsx(self.HEADERS, [[
            "Jane Doe", "Class 99", 2026, "", "Female",
            "", "", "", "", "", "", "", "", "Active",
        ]])
        result = self.admin._process_bulk_upload(upload)
        self.assertEqual(result["created_count"], 0)
        self.assertTrue(any("no class matching" in e for e in result["errors"]))

    def test_unknown_batch_is_skipped_with_error(self):
        upload = _make_xlsx(self.HEADERS, [[
            "Jane Doe", "Class 6", 2026, "Evening (doesn't exist)", "Female",
            "", "", "", "", "", "", "", "", "Active",
        ]])
        result = self.admin._process_bulk_upload(upload)
        self.assertEqual(result["created_count"], 0)
        self.assertTrue(any("no batch matching" in e for e in result["errors"]))

    def test_blank_rows_are_skipped_without_error(self):
        upload = _make_xlsx(self.HEADERS, [
            [None] * len(self.HEADERS),
            ["Jane Doe", "Class 6", 2026, "Morning", "Female",
             "", "", "", "", "", "", "", "", "Active"],
        ])
        result = self.admin._process_bulk_upload(upload)
        self.assertEqual(result["created_count"], 1)
        self.assertEqual(result["errors"], [])

    def test_wrong_headers_are_rejected_before_touching_any_row(self):
        upload = _make_xlsx(["Wrong", "Headers"], [["a", "b"]])
        result = self.admin._process_bulk_upload(upload)
        self.assertEqual(result["created_count"], 0)
        self.assertTrue(any("don't match the template" in e for e in result["errors"]))

    def test_not_an_excel_file_fails_gracefully(self):
        garbage = BytesIO(b"this is not a real xlsx file")
        result = self.admin._process_bulk_upload(garbage)
        self.assertEqual(result["created_count"], 0)
        self.assertTrue(result["errors"])  # a friendly message, not a crash

    def test_sequential_rows_in_same_class_and_batch_get_distinct_codes(self):
        upload = _make_xlsx(self.HEADERS, [
            ["Student A", "Class 6", 2026, "Morning", "", "", "", "", "", "", "", "", "", "Active"],
            ["Student B", "Class 6", 2026, "Morning", "", "", "", "", "", "", "", "", "", "Active"],
        ])
        result = self.admin._process_bulk_upload(upload)
        self.assertEqual(result["created_count"], 2)
        codes = set(Student.objects.values_list("student_code", flat=True))
        self.assertEqual(len(codes), 2)  # no collision between the two rows


class ExamResultBulkUploadTests(TestCase):
    """
    Covers ExamResultAdmin._process_bulk_upload — the mark-sheet parser,
    including the update_or_create re-upload behavior that's easy to
    accidentally break into duplicate rows or silent overwrites.
    """

    def setUp(self):
        self.admin = ExamResultAdmin(ExamResult, admin.site)
        self.klass = Class.objects.create(class_name="Class 7", academic_year=2026)
        self.batch = Batch.objects.create(class_obj=self.klass, batch_name="Morning")
        self.subject = Subject.objects.create(class_obj=self.klass, subject_name="Physics")
        self.exam = Exam.objects.create(
            class_obj=self.klass, exam_name="Midterm", exam_date="2026-06-01"
        )
        self.student = Student.objects.create(
            student_code="PiC7B1001", class_obj=self.klass, batch=self.batch,
            full_name="Test Student",
        )

    def test_valid_marks_create_exam_result(self):
        upload = _make_xlsx(
            ["Student ID", "Full Name", "Physics"],
            [["PiC7B1001", "Test Student", 85]],
        )
        result = self.admin._process_bulk_upload(upload, self.exam)
        self.assertEqual(result["saved_count"], 1)
        self.assertEqual(result["errors"], [])
        er = ExamResult.objects.get(exam=self.exam, student=self.student, subject=self.subject)
        self.assertEqual(er.marks, 85)

    def test_reuploading_corrected_marks_updates_not_duplicates(self):
        headers = ["Student ID", "Full Name", "Physics"]
        first = _make_xlsx(headers, [["PiC7B1001", "Test Student", 60]])
        self.admin._process_bulk_upload(first, self.exam)

        corrected = _make_xlsx(headers, [["PiC7B1001", "Test Student", 92]])
        result = self.admin._process_bulk_upload(corrected, self.exam)

        self.assertEqual(result["saved_count"], 1)
        self.assertEqual(
            ExamResult.objects.filter(exam=self.exam, student=self.student, subject=self.subject).count(),
            1,  # updated in place, not a second row
        )
        er = ExamResult.objects.get(exam=self.exam, student=self.student, subject=self.subject)
        self.assertEqual(er.marks, 92)

    def test_unrecognized_subject_column_is_flagged_not_silently_dropped(self):
        upload = _make_xlsx(
            ["Student ID", "Full Name", "Chemistry"],  # not in this class
            [["PiC7B1001", "Test Student", 70]],
        )
        result = self.admin._process_bulk_upload(upload, self.exam)
        self.assertEqual(result["saved_count"], 0)
        self.assertTrue(any("Chemistry" in e for e in result["errors"]))

    def test_non_numeric_marks_are_skipped_with_error(self):
        upload = _make_xlsx(
            ["Student ID", "Full Name", "Physics"],
            [["PiC7B1001", "Test Student", "absent"]],
        )
        result = self.admin._process_bulk_upload(upload, self.exam)
        self.assertEqual(result["saved_count"], 0)
        self.assertTrue(any("isn't a number" in e for e in result["errors"]))

    def test_negative_marks_are_rejected(self):
        upload = _make_xlsx(
            ["Student ID", "Full Name", "Physics"],
            [["PiC7B1001", "Test Student", -5]],
        )
        result = self.admin._process_bulk_upload(upload, self.exam)
        self.assertEqual(result["saved_count"], 0)
        self.assertTrue(any("negative" in e for e in result["errors"]))

    def test_unknown_student_id_is_skipped_with_error(self):
        upload = _make_xlsx(
            ["Student ID", "Full Name", "Physics"],
            [["DOES-NOT-EXIST", "Nobody", 70]],
        )
        result = self.admin._process_bulk_upload(upload, self.exam)
        self.assertEqual(result["saved_count"], 0)
        self.assertTrue(any("no student" in e for e in result["errors"]))


class ExpenseFormTests(TestCase):
    def _data(self, **overrides):
        data = {
            "title": "Office rent",
            "category": "Rent",
            "amount": "12000",
            "expense_date": date.today().isoformat(),
            "payment_method": "Cash",
            "remarks": "",
        }
        data.update(overrides)
        return data

    def test_valid_expense(self):
        self.assertTrue(ExpenseForm(data=self._data()).is_valid())

    def test_zero_and_negative_amounts_rejected(self):
        self.assertFalse(ExpenseForm(data=self._data(amount="0")).is_valid())
        self.assertFalse(ExpenseForm(data=self._data(amount="-50")).is_valid())

    def test_future_date_rejected(self):
        future = (date.today() + timedelta(days=3)).isoformat()
        self.assertFalse(ExpenseForm(data=self._data(expense_date=future)).is_valid())

    def test_amount_is_rounded_to_whole_taka(self):
        form = ExpenseForm(data=self._data(amount="150.40"))
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data["amount"], 150)


class FinanceSummaryTests(TestCase):
    """Income = receipts (minus discount) + legacy payments.
    Expenses = salaries actually PAID + other expenses. Net = difference."""

    def setUp(self):
        klass = Class.objects.create(class_name="Class 6", academic_year=2026)
        self.student = Student.objects.create(
            student_code="PiC6B0001", class_obj=klass, full_name="Test Student"
        )
        self.teacher = Faculty.objects.create(full_name="Test Teacher")
        self.today = date.today()

    def _receipt(self, total, discount, when=None, number=None):
        return StudentPaymentReceipt.objects.create(
            student=self.student, payment_date=when or self.today,
            items=[], total_amount=total, total_discount=discount,
            receipt_number=number,
        )

    def test_income_subtracts_receipt_discount(self):
        self._receipt(3000, 500, number="PAY-T-1")
        self.assertEqual(_finance_summary()["income"], 2500)

    def test_legacy_payments_count_as_income(self):
        StudentPayment.objects.create(
            student=self.student, payment_type="Monthly Fee",
            amount=1000, payment_date=self.today,
        )
        self._receipt(2000, 0, number="PAY-T-2")
        self.assertEqual(_finance_summary()["income"], 3000)

    def test_only_paid_salary_counts_as_expense(self):
        TeacherSalary.objects.create(
            teacher=self.teacher, salary_month=self.today.replace(day=1),
            amount=6000, net_salary=6000, paid_amount=4000, due_amount=2000,
            payment_date=self.today,
        )
        summary = _finance_summary()
        self.assertEqual(summary["salaries_paid"], 4000)

    def test_unpaid_salary_is_not_an_expense(self):
        TeacherSalary.objects.create(
            teacher=self.teacher, salary_month=self.today.replace(day=1),
            amount=6000, net_salary=6000, paid_amount=0, due_amount=6000,
        )
        self.assertEqual(_finance_summary()["salaries_paid"], 0)

    def test_net_is_income_minus_all_expenses(self):
        self._receipt(10000, 1000, number="PAY-T-3")  # income 9000
        TeacherSalary.objects.create(
            teacher=self.teacher, salary_month=self.today.replace(day=1),
            amount=3000, net_salary=3000, paid_amount=3000, due_amount=0,
            payment_date=self.today,
        )
        Expense.objects.create(
            title="Rent", category="Rent", amount=2000, expense_date=self.today,
        )
        summary = _finance_summary()
        self.assertEqual(summary["income"], 9000)
        self.assertEqual(summary["expenses"], 5000)
        self.assertEqual(summary["net"], 4000)

    def test_net_can_go_negative(self):
        Expense.objects.create(
            title="Repairs", category="Maintenance", amount=500, expense_date=self.today,
        )
        self.assertEqual(_finance_summary()["net"], -500)

    def test_date_range_excludes_other_months(self):
        old = self.today - timedelta(days=90)
        self._receipt(5000, 0, when=old, number="PAY-T-4")
        Expense.objects.create(title="Old", category="Other", amount=700, expense_date=old)
        window = _finance_summary(self.today - timedelta(days=30), self.today)
        self.assertEqual(window["income"], 0)
        self.assertEqual(window["expenses"], 0)


class ExpenseAdminTests(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model
        self.admin_user = get_user_model().objects.create_superuser(
            "boss", "boss@example.com", "pw12345!"
        )
        self.client.force_login(self.admin_user)

    def test_add_expense_through_admin(self):
        response = self.client.post(reverse("admin:core_expense_add"), {
            "title": "Markers", "category": "Supplies", "amount": "250",
            "expense_date": date.today().isoformat(), "payment_method": "Cash",
            "remarks": "",
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Expense.objects.get().amount, 250)

    def test_list_and_delete(self):
        expense = Expense.objects.create(
            title="Tea", category="Events", amount=90, expense_date=date.today(),
        )
        self.assertEqual(self.client.get(reverse("admin:core_expense_changelist")).status_code, 200)
        self.client.post(reverse("admin:core_expense_delete", args=[expense.pk]))
        self.assertFalse(Expense.objects.exists())

    def test_dashboard_shows_income_expenses_and_net(self):
        Expense.objects.create(
            title="Rent", category="Rent", amount=800, expense_date=date.today(),
        )
        response = self.client.get(reverse("admin:index"))
        self.assertEqual(response.status_code, 200)
        finance = response.context["dashboard_finance"]
        self.assertEqual(finance["month"]["expenses"], 800)
        self.assertEqual(finance["month"]["net"], -800)
        self.assertContains(response, "Net revenue")


class StudentAdmissionFieldsTests(TestCase):
    def setUp(self):
        self.klass = Class.objects.create(class_name="Class 8", academic_year=2026)

    def _data(self, **overrides):
        data = {
            "class_obj": self.klass.pk, "full_name": "Rahim Uddin",
            "date_of_birth": "2012-03-10", "admission_date": date.today().isoformat(),
            "institution_name": "Dhaka Residential School", "blood_group": "O+",
            "reference": "", "status": "Active",
        }
        data.update(overrides)
        return data

    def test_valid_new_admission_with_reference_left_blank(self):
        from .forms import StudentForm
        self.assertTrue(StudentForm(data=self._data()).is_valid())

    def test_new_admission_requires_dob_admission_date_school_and_blood_group(self):
        from .forms import StudentForm
        for field in ("date_of_birth", "admission_date", "institution_name", "blood_group"):
            form = StudentForm(data=self._data(**{field: ""}))
            self.assertFalse(form.is_valid(), field)
            self.assertIn(field, form.errors)

    def test_invalid_blood_group_rejected(self):
        from .forms import StudentForm
        self.assertFalse(StudentForm(data=self._data(blood_group="Z+")).is_valid())

    def test_legacy_student_without_new_fields_can_still_be_edited(self):
        from .forms import StudentForm
        legacy = Student.objects.create(
            student_code="PiC8B0001", class_obj=self.klass, full_name="Old Student",
        )
        form = StudentForm(
            data={"class_obj": self.klass.pk, "full_name": "Old Student", "status": "Left"},
            instance=legacy,
        )
        self.assertTrue(form.is_valid(), form.errors)

    def test_existing_value_cannot_be_blanked_out(self):
        from .forms import StudentForm
        student = Student.objects.create(
            student_code="PiC8B0002", class_obj=self.klass, full_name="Has Data",
            blood_group="A+", institution_name="X School",
            date_of_birth=date(2012, 1, 1), admission_date=date.today(),
        )
        form = StudentForm(
            data=self._data(full_name="Has Data", blood_group=""), instance=student,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("blood_group", form.errors)


class StudentBulkUploadNewFieldsTests(TestCase):
    """Bulk upload with the School/College, Blood Group and Reference
    columns, plus the cell-cleaning fixes (phones, dates, status)."""

    from .admin import BULK_STUDENT_HEADERS as NEW_HEADERS  # 17 columns

    def setUp(self):
        self.admin = StudentAdmin(Student, admin.site)
        self.klass = Class.objects.create(class_name="Class 6", academic_year=2026)
        Batch.objects.create(class_obj=self.klass, batch_name="Morning")

    def _row(self, **o):
        row = {
            "name": "Jane Doe", "gender": "Female", "dob": "2014-05-12",
            "phone": "01700000000", "adm": "2026-01-10", "status": "Active",
            "school": "Dhaka Residential School", "blood": "O+", "ref": "",
        }
        row.update(o)
        return [
            row["name"], "Class 6", 2026, "Morning", row["gender"], row["dob"],
            row["phone"], "", "", "", "", "", row["adm"], row["status"],
            row["school"], row["blood"], row["ref"],
        ]

    def _run(self, *rows):
        return self.admin._process_bulk_upload(_make_xlsx(self.NEW_HEADERS, list(rows)))

    def test_template_has_seventeen_columns_new_ones_last(self):
        self.assertEqual(len(self.NEW_HEADERS), 17)
        self.assertEqual(self.NEW_HEADERS[14:], [
            "School / College Name", "Blood Group", "Reference (optional)",
        ])

    def test_new_fields_are_saved(self):
        result = self._run(self._row(ref="Karim sir"))
        self.assertEqual(result["errors"], [])
        s = Student.objects.get(full_name="Jane Doe")
        self.assertEqual((s.institution_name, s.blood_group, s.reference),
                         ("Dhaka Residential School", "O+", "Karim sir"))

    def test_reference_is_optional(self):
        self.assertEqual(self._run(self._row(ref=""))["created_count"], 1)

    def test_blood_group_is_normalized(self):
        self._run(self._row(blood=" ab - "))
        self.assertEqual(Student.objects.get().blood_group, "AB-")

    def test_unknown_blood_group_is_skipped_with_error(self):
        result = self._run(self._row(blood="Z+"))
        self.assertEqual(result["created_count"], 0)
        self.assertTrue(any("Blood Group" in e for e in result["errors"]))

    def test_required_fields_enforced_with_new_template(self):
        for field, label in (("dob", "Date of Birth"), ("adm", "Admission Date"),
                             ("school", "School / College Name"), ("blood", "Blood Group")):
            Student.objects.all().delete()
            result = self._run(self._row(**{field: ""}))
            self.assertEqual(result["created_count"], 0, field)
            self.assertTrue(any(label in e for e in result["errors"]), field)

    def test_old_14_column_file_still_accepted_without_new_fields(self):
        legacy = StudentBulkUploadTests.HEADERS
        upload = _make_xlsx(legacy, [[
            "Old Style", "Class 6", 2026, "Morning", "", "", "", "", "", "", "", "", "", "Active",
        ]])
        result = self.admin._process_bulk_upload(upload)
        self.assertEqual(result["created_count"], 1)
        self.assertEqual(result["errors"], [])

    def test_partial_or_misnamed_new_columns_rejected(self):
        headers = StudentBulkUploadTests.HEADERS + ["School / College Name", "Wrong", "Reference (optional)"]
        result = self.admin._process_bulk_upload(_make_xlsx(headers, []))
        self.assertEqual(result["created_count"], 0)
        self.assertTrue(any("new columns" in e for e in result["errors"]))

    def test_numeric_phone_cells_get_their_leading_zero_back(self):
        self._run(self._row(phone=1700000000), )
        self.assertEqual(Student.objects.get().student_phone, "01700000000")
        Student.objects.all().delete()
        self._run(self._row(phone=1700000000.0))
        self.assertEqual(Student.objects.get().student_phone, "01700000000")

    def test_unreadable_date_is_flagged_not_dropped(self):
        result = self._run(self._row(dob="12th May"))
        self.assertEqual(result["created_count"], 0)
        self.assertTrue(any("Date of Birth" in e for e in result["errors"]))

    def test_unknown_status_and_gender_are_flagged_not_defaulted(self):
        result = self._run(self._row(status="Enrolled"), self._row(name="B", gender="Robot"))
        self.assertEqual(result["created_count"], 0)
        self.assertTrue(any("Status" in e for e in result["errors"]))
        self.assertTrue(any("Gender" in e for e in result["errors"]))

    def test_downloaded_template_matches_upload_format(self):
        from django.contrib.auth import get_user_model
        user = get_user_model().objects.create_superuser("boss", "b@x.com", "pw12345!")
        self.client.force_login(user)
        response = self.client.get(reverse("admin:core_student_bulk_template"))
        self.assertEqual(response.status_code, 200)
        sheet = openpyxl.load_workbook(BytesIO(response.content)).active
        self.assertEqual([c.value for c in sheet[1]], self.NEW_HEADERS)
        # the sample row in the template must itself upload cleanly
        result = self.admin._process_bulk_upload(BytesIO(response.content))
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["created_count"], 1)