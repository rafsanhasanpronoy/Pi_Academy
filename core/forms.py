from datetime import date

from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError

from .models import (
    Achievement, AdmissionInfo, AdmissionInquiry, Batch, Class, ClassSchedule,
    ContactMessage, Exam, ExamResult, Faculty, Gallery, GallerySection, GallerySubsection,
    Notice, Student, StudentPayment, Subject, TeacherSalary,
)

INPUT_CLASSES = (
    "w-full border border-ink/15 bg-white px-4 py-3 text-ink "
    "placeholder:text-ink/40 focus:outline-none focus:border-brand "
    "focus:ring-1 focus:ring-brand transition-colors"
)


class TailwindStyledFormMixin:
    """Applies consistent input styling to every visible field."""

    def _style_fields(self):
        for name, field in self.fields.items():
            # Radio buttons / checkboxes get their own styling (see
            # .radio-group in dashboard_base.html) — the text-input
            # classes would make each circle look like a stretched box.
            if isinstance(field.widget, (forms.RadioSelect, forms.CheckboxSelectMultiple, forms.CheckboxInput)):
                continue
            existing = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = (existing + " " + INPUT_CLASSES).strip()
            if isinstance(field.widget, forms.Textarea):
                field.widget.attrs.setdefault("rows", 4)


class MultipleFileInput(forms.ClearableFileInput):
    """A <input type=file multiple> widget. Paired with MultipleFileField
    below — Django's built-in FileField only ever cleans a single upload,
    so both pieces are needed to accept more than one file per submit."""

    allow_multiple_selected = True

    def __init__(self, attrs=None):
        attrs = {**(attrs or {}), "multiple": True}
        super().__init__(attrs)


class MultipleFileField(forms.FileField):
    widget = MultipleFileInput

    def clean(self, data, initial=None):
        single_file_clean = super().clean
        if isinstance(data, (list, tuple)):
            return [single_file_clean(d, initial) for d in data]
        return single_file_clean(data, initial)


class HoneypotMixin(forms.Form):
    """
    Adds an invisible field that only bots fill in. A human never sees
    it (hidden via CSS in the template, not just an HTML `hidden` input,
    since some bots skip those), so if it arrives non-empty we know the
    submission is spam and can quietly reject it — no CAPTCHA needed for
    this class of bot.

    Usage in the template: render {{ form.website }} inside a wrapper
    styled `class="hidden"` (see updated contact.html / admission.html).
    """

    website = forms.CharField(
        required=False,
        label="",
        widget=forms.TextInput(attrs={
            "autocomplete": "off",
            "tabindex": "-1",
        }),
    )

    def clean_website(self):
        value = self.cleaned_data.get("website")
        if value:
            # Don't tell the bot what tripped — just fail validation.
            raise ValidationError("Submission rejected.")
        return value


class AdmissionInquiryForm(TailwindStyledFormMixin, HoneypotMixin, forms.ModelForm):
    class Meta:
        model = AdmissionInquiry
        fields = [
            "student_name",
            "student_phone",
            "guardian_name",
            "guardian_phone",
            "class_obj",
            "message",
        ]
        labels = {
            "student_name": "Student's name",
            "student_phone": "Student's phone",
            "guardian_name": "Guardian's name",
            "guardian_phone": "Guardian's phone",
            "class_obj": "Class applying for",
            "message": "Anything you'd like us to know",
        }
        widgets = {
            "message": forms.Textarea(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["guardian_name"].required = False
        self.fields["guardian_phone"].required = False
        self.fields["message"].required = False
        self.fields["class_obj"].required = False
        self.fields["class_obj"].empty_label = "Select a class"
        self._style_fields()


class ContactMessageForm(TailwindStyledFormMixin, HoneypotMixin, forms.ModelForm):
    class Meta:
        model = ContactMessage
        fields = ["name", "phone", "email", "message"]
        widgets = {
            "message": forms.Textarea(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["phone"].required = False
        self.fields["email"].required = False
        self._style_fields()

    def clean(self):
        cleaned_data = super().clean()
        phone = cleaned_data.get("phone")
        email = cleaned_data.get("email")
        # Both are individually optional, but staff need SOME way to
        # reply — without this, a visitor can submit a message that's
        # impossible to respond to.
        if not phone and not email:
            raise ValidationError(
                "Please provide a phone number or an email so we can reply to you."
            )
        return cleaned_data


class StudentLookupForm(TailwindStyledFormMixin, forms.Form):
    student_code = forms.CharField(
        label="Student ID",
        max_length=30,
        widget=forms.TextInput(attrs={"placeholder": "e.g. STU-2026-014"}),
    )
    student_phone = forms.CharField(
        label="Phone Number",
        max_length=20,
        widget=forms.TextInput(attrs={"placeholder": "The phone number on file"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()


class ClassForm(TailwindStyledFormMixin, forms.ModelForm):
    """Used by admin.ClassAdmin's custom add/change views."""

    class Meta:
        model = Class
        fields = ["class_name", "academic_year"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()


class BatchForm(TailwindStyledFormMixin, forms.ModelForm):
    """Used by admin.BatchAdmin's custom add/change views."""

    class Meta:
        model = Batch
        fields = ["class_obj", "batch_name", "room", "start_time", "end_time"]
        widgets = {
            "start_time": forms.TimeInput(attrs={"type": "time"}),
            "end_time": forms.TimeInput(attrs={"type": "time"}),
        }

    def __init__(self, *args, lock_class=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["class_obj"].label = "Class"
        # When arriving from a specific class's "Add a batch" link, the
        # class is already known — lock it as a hidden field instead of
        # making staff pick it again from the dropdown.
        if lock_class is not None:
            self.fields["class_obj"].initial = lock_class.pk
            self.fields["class_obj"].widget = forms.HiddenInput()
        self._style_fields()

    def clean(self):
        cleaned_data = super().clean()
        start_time = cleaned_data.get("start_time")
        end_time = cleaned_data.get("end_time")
        # The database enforces end_time > start_time via a check
        # constraint (valid_batch_time) — validate it here too so staff
        # get a clear inline error instead of a 500 from the DB.
        if start_time and end_time and end_time <= start_time:
            raise ValidationError("End time must be after start time.")
        return cleaned_data


class FacultyForm(TailwindStyledFormMixin, forms.ModelForm):
    """Used by admin.FacultyAdmin's custom add/change views."""

    photo_upload = forms.ImageField(
        required=False,
        label="Upload Photo",
        help_text="Uploading a file replaces whatever is in Photo URL below.",
    )

    class Meta:
        model = Faculty
        fields = ["full_name", "photo_url", "designation", "phone", "email", "joining_date"]
        widgets = {
            "joining_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["joining_date"].input_formats = ["%Y-%m-%d"]
        self.fields["designation"].required = False
        self.fields["phone"].required = False
        self.fields["email"].required = False
        self.fields["photo_url"].required = False
        self.fields["photo_url"].label = "Photo URL (or paste a link instead)"
        self.fields["photo_url"].widget = forms.TextInput(attrs={"placeholder": "https://..."})
        self.order_fields(
            ["full_name", "photo_upload", "photo_url", "designation", "phone", "email", "joining_date"]
        )
        self._style_fields()

    def save(self, commit=True):
        instance = super().save(commit=False)
        uploaded = self.cleaned_data.get("photo_upload")
        if uploaded:
            from django.core.files.storage import default_storage

            path = default_storage.save(f"faculty/{uploaded.name}", uploaded)
            instance.photo_url = default_storage.url(path)
        if commit:
            instance.save()
        return instance


class SubjectForm(TailwindStyledFormMixin, forms.ModelForm):
    """
    Used by admin.SubjectAdmin's custom add/change views.

    subject_code is deliberately excluded — it's generated automatically
    from subject_name + class_obj (see admin._generate_subject_code) and
    never typed in by staff.
    """

    class Meta:
        model = Subject
        fields = ["class_obj", "subject_name"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["class_obj"].label = "Class"
        self.fields["class_obj"].empty_label = "Select a class"
        self._style_fields()


class StudentForm(TailwindStyledFormMixin, forms.ModelForm):
    """
    Used by admin.StudentAdmin's custom add/change views.

    student_code is deliberately excluded — it's generated automatically
    (see admin._generate_student_code) and never typed in by staff.
    """

    GENDER_CHOICES = [
        ("Male", "Male"),
        ("Female", "Female"),
        ("Other", "Other"),
    ]

    gender = forms.ChoiceField(
        choices=GENDER_CHOICES,
        required=False,
        widget=forms.RadioSelect,
    )

    photo_upload = forms.ImageField(
        required=False,
        label="Upload Photo",
        help_text="Optional. Uploading a file replaces whatever is in Photo URL below.",
    )

    class Meta:
        model = Student
        fields = [
            "class_obj",
            "batch",
            "full_name",
            "photo_url",
            "gender",
            "date_of_birth",
            "student_phone",
            "father_name",
            "father_phone",
            "mother_name",
            "mother_phone",
            "address",
            "admission_date",
            "status",
        ]
        widgets = {
            # type="date" gives every browser's native date picker instead
            # of a free-text box that silently rejects the wrong format —
            # this was the root cause of the earlier DOB entry issues.
            "date_of_birth": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "admission_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "address": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Accept the ISO format the date input sends back, regardless of
        # server locale.
        self.fields["date_of_birth"].input_formats = ["%Y-%m-%d"]
        self.fields["admission_date"].input_formats = ["%Y-%m-%d"]

        self.fields["class_obj"].label = "Class"
        self.fields["class_obj"].empty_label = "Select a class"
        self.fields["batch"].required = False
        self.fields["batch"].empty_label = "Select a batch (optional)"
        self.fields["photo_url"].required = False
        self.fields["photo_url"].label = "Photo URL (or paste a link instead)"
        self.fields["photo_url"].widget = forms.TextInput(attrs={"placeholder": "https://..."})
        for name in ("student_phone", "father_name", "father_phone",
                     "mother_name", "mother_phone", "address", "admission_date"):
            self.fields[name].required = False

        self._style_fields()

    def clean_date_of_birth(self):
        dob = self.cleaned_data.get("date_of_birth")
        if dob:
            if dob > date.today():
                raise ValidationError("Date of birth can't be in the future.")
            age_years = (date.today() - dob).days / 365.25
            if age_years > 100:
                raise ValidationError("Please double-check this date — it's over 100 years ago.")
        return dob

    def clean_admission_date(self):
        admitted = self.cleaned_data.get("admission_date")
        if admitted and admitted > date.today():
            raise ValidationError("Admission date can't be in the future.")
        return admitted

    def save(self, commit=True):
        instance = super().save(commit=False)
        uploaded = self.cleaned_data.get("photo_upload")
        if uploaded:
            from django.core.files.storage import default_storage

            path = default_storage.save(f"students/{uploaded.name}", uploaded)
            instance.photo_url = default_storage.url(path)
        if commit:
            instance.save()
        return instance


class StudentPaymentForm(TailwindStyledFormMixin, forms.ModelForm):
    """Used by admin.StudentPaymentAdmin's custom add/change views."""

    class Meta:
        model = StudentPayment
        fields = [
            "student",
            "payment_type",
            "amount",
            "payment_date",
            "payment_month",
            "remarks",
        ]
        widgets = {
            # type="date"/"month" give native pickers instead of a
            # free-text box that silently rejects the wrong format —
            # same reasoning as StudentForm's date fields.
            "payment_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "payment_month": forms.DateInput(attrs={"type": "month"}, format="%Y-%m"),
            "remarks": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, lock_student=None, **kwargs):
        super().__init__(*args, **kwargs)
        # Accept back the ISO formats the date/month inputs send, regardless
        # of server locale.
        self.fields["payment_date"].input_formats = ["%Y-%m-%d"]
        self.fields["payment_month"].input_formats = ["%Y-%m", "%Y-%m-%d"]

        self.fields["student"].empty_label = "Select a student"
        self.fields["payment_month"].required = False
        self.fields["payment_month"].help_text = "Only needed for Monthly Fee payments."
        self.fields["remarks"].required = False

        # When arriving from a specific student's "Record a payment" link
        # (or the Monthly Fee Status report), the student is already
        # known — lock it as a hidden field instead of making staff pick
        # them again from the dropdown.
        if lock_student is not None:
            self.fields["student"].initial = lock_student.pk
            self.fields["student"].widget = forms.HiddenInput()

        self._style_fields()

    def clean(self):
        cleaned_data = super().clean()
        payment_type = cleaned_data.get("payment_type")
        payment_month = cleaned_data.get("payment_month")
        # Monthly Fee is the only recurring charge, and the Monthly Fee
        # Status report groups payments by payment_month — without it, a
        # monthly payment would silently never show up as "paid" there.
        if payment_type == "Monthly Fee" and not payment_month:
            raise ValidationError("Please select which month this payment covers.")
        return cleaned_data


class TeacherSalaryForm(TailwindStyledFormMixin, forms.ModelForm):
    """Used by admin.TeacherSalaryAdmin's custom add/change views.

    net_salary, due_amount, attendance_deduction, and status are all
    computed here in save() rather than typed in — see the comments
    below. receipt_number is generated in admin.py (same pattern as
    Student.student_code), not here.
    """

    class Meta:
        model = TeacherSalary
        fields = [
            "teacher", "salary_month",
            "gross_salary", "bonus", "deduction",
            "present_days", "absent_days", "late_days",
            "payment_method", "paid_amount", "transaction_id",
            "payment_date", "remarks",
        ]
        widgets = {
            "salary_month": forms.DateInput(attrs={"type": "month"}, format="%Y-%m"),
            "payment_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "remarks": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, lock_teacher=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["salary_month"].input_formats = ["%Y-%m", "%Y-%m-%d"]
        self.fields["payment_date"].input_formats = ["%Y-%m-%d"]

        self.fields["teacher"].empty_label = "Select a faculty member"
        self.fields["payment_date"].required = False
        self.fields["payment_date"].help_text = "Set this once at least part of the salary has been paid out."
        self.fields["remarks"].required = False
        self.fields["transaction_id"].required = False
        self.fields["transaction_id"].help_text = "Bank/mobile-wallet transaction reference, if applicable."

        self.fields["bonus"].required = False
        self.fields["deduction"].required = False
        self.fields["deduction"].label = "Other deductions"
        self.fields["deduction"].help_text = "Anything besides attendance — an advance, a fine, etc."
        self.fields["paid_amount"].required = False

        for name in ("present_days", "absent_days", "late_days"):
            self.fields[name].required = False
            self.fields[name].widget.attrs.setdefault("min", 0)
        self.fields["present_days"].help_text = "Manual entry — this project doesn't track teacher attendance automatically."
        self.fields["absent_days"].help_text = f"Deducted at ৳{settings.ABSENT_DEDUCTION_PER_DAY}/day."
        self.fields["late_days"].help_text = f"Deducted at ৳{settings.LATE_DEDUCTION_PER_DAY}/day."

        if not self.instance.pk:
            # Every faculty member is on the same fixed monthly rate for
            # now — pre-fill it but leave it editable, since that won't
            # always be true (a raise, a part-time rate, etc).
            self.fields["gross_salary"].initial = 15000

        # Arriving from a specific faculty member's "Record Salary" link
        # (or the Monthly Salary Status report), the teacher is already
        # known — lock it as a hidden field instead of making staff pick
        # them again from the dropdown.
        if lock_teacher is not None:
            self.fields["teacher"].initial = lock_teacher.pk
            self.fields["teacher"].widget = forms.HiddenInput()

        self._style_fields()

    # These six fields are all required=False above for a nicer form (an
    # admin shouldn't have to type "0" into Bonus just to leave it out),
    # but the DB columns are NOT NULL with default=0 — an empty submission
    # otherwise becomes None here and crashes instance.save() with a raw
    # IntegrityError instead of a clean validation message.
    def clean_bonus(self):
        return self.cleaned_data.get("bonus") or 0

    def clean_deduction(self):
        return self.cleaned_data.get("deduction") or 0

    def clean_paid_amount(self):
        return self.cleaned_data.get("paid_amount") or 0

    def clean_present_days(self):
        return self.cleaned_data.get("present_days") or 0

    def clean_absent_days(self):
        return self.cleaned_data.get("absent_days") or 0

    def clean_late_days(self):
        return self.cleaned_data.get("late_days") or 0

    def clean(self):
        cleaned_data = super().clean()
        teacher = cleaned_data.get("teacher")
        salary_month = cleaned_data.get("salary_month")

        # Mirrors the DB's unique_together(teacher, salary_month) with a
        # clear inline message instead of a raw IntegrityError.
        if teacher and salary_month:
            clash = TeacherSalary.objects.filter(teacher=teacher, salary_month=salary_month)
            if self.instance.pk:
                clash = clash.exclude(pk=self.instance.pk)
            if clash.exists():
                raise ValidationError(
                    f"{teacher.full_name} already has a salary record for "
                    f"{salary_month:%B %Y}."
                )

        gross_salary = cleaned_data.get("gross_salary") or 0
        bonus = cleaned_data.get("bonus") or 0
        deduction = cleaned_data.get("deduction") or 0
        absent_days = cleaned_data.get("absent_days") or 0
        late_days = cleaned_data.get("late_days") or 0
        paid_amount = cleaned_data.get("paid_amount") or 0

        attendance_deduction = (
            absent_days * settings.ABSENT_DEDUCTION_PER_DAY
            + late_days * settings.LATE_DEDUCTION_PER_DAY
        )
        net_salary = gross_salary + bonus - deduction - attendance_deduction

        if paid_amount > net_salary:
            raise ValidationError(
                f"Paid amount (৳{paid_amount}) can't exceed net salary (৳{net_salary})."
            )

        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)

        instance.attendance_deduction = (
            (instance.absent_days or 0) * settings.ABSENT_DEDUCTION_PER_DAY
            + (instance.late_days or 0) * settings.LATE_DEDUCTION_PER_DAY
        )
        instance.net_salary = (
            (instance.gross_salary or 0) + (instance.bonus or 0)
            - (instance.deduction or 0) - instance.attendance_deduction
        )
        instance.due_amount = max(instance.net_salary - (instance.paid_amount or 0), 0)

        if instance.net_salary > 0 and instance.due_amount <= 0:
            instance.status = "Paid"
        elif instance.paid_amount and instance.paid_amount > 0:
            instance.status = "Partial"
        else:
            instance.status = "Pending"

        # Keep the legacy flat `amount` column in sync for anything that
        # might still read it, without exposing it in the form.
        instance.amount = instance.net_salary

        if commit:
            instance.save()
        return instance


class ExamForm(TailwindStyledFormMixin, forms.ModelForm):
    """Used by admin.ExamAdmin's custom add/change views."""

    class Meta:
        model = Exam
        fields = ["class_obj", "exam_name", "exam_date"]
        widgets = {
            "exam_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["exam_date"].input_formats = ["%Y-%m-%d"]
        self.fields["class_obj"].label = "Class"
        self.fields["class_obj"].empty_label = "Select a class"
        self._style_fields()


class ExamResultForm(TailwindStyledFormMixin, forms.ModelForm):
    """Used by admin.ExamResultAdmin's custom add/change views."""

    class Meta:
        model = ExamResult
        fields = ["exam", "student", "subject", "marks", "grade"]

    def __init__(self, *args, lock_exam=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["exam"].empty_label = "Select an exam"
        self.fields["student"].empty_label = "Select a student"
        self.fields["subject"].empty_label = "Select a subject"
        self.fields["grade"].required = False

        # Arriving from a specific exam's "Add Result" link — the exam
        # (and therefore its class) is already known. Lock it as a hidden
        # field and narrow Student/Subject to that class, same reasoning
        # as ClassScheduleForm's lock_class.
        active_exam = lock_exam or (self.instance.exam if self.instance.pk else None)
        if lock_exam is not None:
            self.fields["exam"].initial = lock_exam.pk
            self.fields["exam"].widget = forms.HiddenInput()
        if active_exam is not None:
            self.fields["student"].queryset = Student.objects.filter(
                class_obj=active_exam.class_obj_id
            ).order_by("full_name")
            self.fields["subject"].queryset = Subject.objects.filter(
                class_obj=active_exam.class_obj_id
            ).order_by("subject_name")

        self._style_fields()

    def clean(self):
        cleaned_data = super().clean()
        exam = cleaned_data.get("exam")
        student = cleaned_data.get("student")
        subject = cleaned_data.get("subject")

        # Mirrors the DB's unique_together(exam, student, subject) with a
        # clear inline message instead of a raw IntegrityError, and makes
        # sure the student/subject picked actually belong to the exam's
        # class (matters if the queryset filtering above was bypassed,
        # e.g. a stale form re-submitted after the exam's class changed).
        if exam and student and student.class_obj_id != exam.class_obj_id:
            raise ValidationError(
                f"{student.full_name} is not in {exam.class_obj.class_name}, "
                f"the class this exam is for."
            )
        if exam and subject and subject.class_obj_id != exam.class_obj_id:
            raise ValidationError(
                f"{subject.subject_name} does not belong to {exam.class_obj.class_name}."
            )
        if exam and student and subject:
            clash = ExamResult.objects.filter(exam=exam, student=student, subject=subject)
            if self.instance.pk:
                clash = clash.exclude(pk=self.instance.pk)
            if clash.exists():
                raise ValidationError(
                    f"{student.full_name} already has a {subject.subject_name} result "
                    f"recorded for this exam."
                )
        return cleaned_data


class ClassScheduleForm(TailwindStyledFormMixin, forms.ModelForm):
    """Used by admin.ClassScheduleAdmin's custom add/change views."""

    class Meta:
        model = ClassSchedule
        fields = [
            "class_obj",
            "day_of_week",
            "subject",
            "batch",
            "room",
            "teacher",
            "start_time",
            "end_time",
            "status",
            "notes",
        ]
        widgets = {
            "start_time": forms.TimeInput(attrs={"type": "time"}),
            "end_time": forms.TimeInput(attrs={"type": "time"}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, lock_batch=None, lock_class=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["class_obj"].label = "Class"
        self.fields["class_obj"].empty_label = "Select a class"
        self.fields["batch"].label = "Batch"
        self.fields["teacher"].label = "Faculty"
        self.fields["room"].required = False
        self.fields["notes"].required = False

        # When arriving from a specific batch's "Add a class" link, the
        # batch (and therefore its class) is already known — lock both
        # as hidden fields instead of making staff pick them again.
        if lock_batch is not None:
            self.fields["batch"].initial = lock_batch.pk
            self.fields["batch"].widget = forms.HiddenInput()
            self.fields["class_obj"].initial = lock_batch.class_obj_id
            self.fields["class_obj"].widget = forms.HiddenInput()
        elif lock_class is not None:
            # Arriving from a specific class's page — class is known,
            # but batch still needs picking.
            self.fields["class_obj"].initial = lock_class.pk
            self.fields["class_obj"].widget = forms.HiddenInput()

        self._style_fields()

    def clean(self):
        cleaned_data = super().clean()
        start_time = cleaned_data.get("start_time")
        end_time = cleaned_data.get("end_time")
        # The database enforces end_time > start_time via a check
        # constraint (valid_class_schedule_time) — validate it here too
        # so staff get a clear inline error instead of a 500 from the DB.
        if start_time and end_time and end_time <= start_time:
            raise ValidationError("End time must be after start time.")

        class_obj = cleaned_data.get("class_obj")
        batch = cleaned_data.get("batch")
        subject = cleaned_data.get("subject")

        # Class is now the source of truth staff pick first — make sure
        # the Batch and Subject chosen actually belong to it.
        if class_obj and batch and batch.class_obj_id != class_obj.id:
            raise ValidationError(
                f"{batch.batch_name} belongs to {batch.class_obj.class_name}, "
                f"not {class_obj.class_name}."
            )
        if class_obj and subject and subject.class_obj_id != class_obj.id:
            raise ValidationError(
                f"{subject.subject_name} belongs to {subject.class_obj.class_name}, "
                f"not {class_obj.class_name}."
            )
        return cleaned_data


class NoticeForm(TailwindStyledFormMixin, forms.ModelForm):
    """Used by admin.NoticeAdmin's custom add/change views."""

    image_upload = forms.ImageField(
        required=False,
        label="Upload Image",
        help_text="Optional. Uploading a file replaces whatever is in Image URL below.",
    )

    class Meta:
        model = Notice
        fields = ["title", "description", "image_url", "published_date", "is_published"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 5}),
            "published_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["published_date"].input_formats = ["%Y-%m-%d"]
        self.fields["is_published"].required = False
        self.fields["image_url"].required = False
        self.fields["image_url"].label = "Image URL (or paste a link instead)"
        self.fields["image_url"].widget = forms.TextInput(attrs={"placeholder": "https://..."})
        self.order_fields(
            ["title", "description", "image_upload", "image_url", "published_date", "is_published"]
        )
        self._style_fields()

    def save(self, commit=True):
        instance = super().save(commit=False)
        uploaded = self.cleaned_data.get("image_upload")
        if uploaded:
            from django.core.files.storage import default_storage

            path = default_storage.save(f"notices/{uploaded.name}", uploaded)
            instance.image_url = default_storage.url(path)
        if commit:
            instance.save()
        return instance


class AchievementForm(TailwindStyledFormMixin, forms.ModelForm):
    """Used by admin.AchievementAdmin's custom add/change views."""

    images_upload = MultipleFileField(
        required=False,
        label="Add Images",
        help_text="Select one or more images (hold Ctrl/Cmd to multi-select). "
        "New uploads are added to the gallery — they don't replace what's already there.",
    )
    remove_images = forms.MultipleChoiceField(
        required=False,
        label="Existing images",
        widget=forms.CheckboxSelectMultiple,
        help_text="Check an image and save to remove it from the gallery.",
    )

    class Meta:
        model = Achievement
        fields = ["title", "description", "achievement_date", "is_published"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 5}),
            "achievement_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["achievement_date"].input_formats = ["%Y-%m-%d"]
        self.fields["description"].required = False
        self.fields["is_published"].required = False

        existing_images = []
        if self.instance and self.instance.pk:
            existing_images = list(self.instance.image_urls or [])
            # Fold in a legacy single `image_url` from before the gallery
            # existed, so old achievements can still have it removed here.
            if self.instance.image_url and self.instance.image_url not in existing_images:
                existing_images.append(self.instance.image_url)
        self.fields["remove_images"].choices = [(url, url) for url in existing_images]

        self.order_fields(
            ["title", "description", "achievement_date", "is_published", "remove_images", "images_upload"]
        )
        self._style_fields()

    def save(self, commit=True):
        instance = super().save(commit=False)

        current = list(instance.image_urls or [])
        if instance.image_url and instance.image_url not in current:
            current.append(instance.image_url)

        removed = set(self.cleaned_data.get("remove_images") or [])
        if removed:
            current = [url for url in current if url not in removed]

        uploaded = self.cleaned_data.get("images_upload") or []
        if uploaded:
            from django.core.files.storage import default_storage

            for f in uploaded:
                path = default_storage.save(f"achievements/{f.name}", f)
                current.append(default_storage.url(path))

        instance.image_urls = current
        # Keep the legacy field in sync (harmless, and avoids stale/duplicate
        # data if anything still reads image_url directly).
        instance.image_url = current[0] if current else None

        if commit:
            instance.save()
        return instance


class GalleryForm(TailwindStyledFormMixin, forms.ModelForm):
    """Used by admin.GalleryAdmin's custom add/change views."""

    image_upload = forms.ImageField(
        required=False,
        label="Upload Image",
        help_text="Uploading a file replaces whatever is in Image URL below.",
    )

    class Meta:
        model = Gallery
        fields = ["title", "image_url", "category", "description", "is_published"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["title"].required = False
        self.fields["category"].required = False
        self.fields["description"].required = False
        self.fields["image_url"].required = False
        self.fields["image_url"].label = "Image URL (or paste a link instead)"
        self.fields["image_url"].widget = forms.TextInput(attrs={"placeholder": "https://..."})
        self.fields["is_published"].required = False
        self.order_fields(
            ["title", "image_upload", "image_url", "category", "description", "is_published"]
        )
        self._style_fields()

    def clean(self):
        cleaned_data = super().clean()
        # The gallery table itself doesn't allow a blank image_url, so
        # unlike Achievement, this one genuinely needs either an upload
        # or a pasted link — not just one field marked required.
        if not cleaned_data.get("image_upload") and not cleaned_data.get("image_url"):
            raise ValidationError("Upload an image or paste an image URL.")
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        uploaded = self.cleaned_data.get("image_upload")
        if uploaded:
            from django.core.files.storage import default_storage

            path = default_storage.save(f"gallery/{uploaded.name}", uploaded)
            instance.image_url = default_storage.url(path)
        if commit:
            instance.save()
        return instance


class GallerySectionForm(TailwindStyledFormMixin, forms.ModelForm):
    """Used by admin.GallerySectionAdmin's custom add/change views."""

    class Meta:
        model = GallerySection
        fields = ["title", "description", "sort_order", "is_published"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["description"].required = False
        self.fields["is_published"].required = False
        self.fields["sort_order"].required = False
        self.fields["sort_order"].help_text = (
            "Lower numbers show first on the public Gallery page. Leave as 0 if the order doesn't matter."
        )
        self._style_fields()


class GallerySubsectionForm(TailwindStyledFormMixin, forms.ModelForm):
    """Used by admin.GallerySubsectionAdmin's custom add/change views.

    Editing existing images (per-image description, removal) is handled
    directly in admin._subsection_form_view from raw POST data, since the
    number of images varies per subsection — a fixed ModelForm field can't
    represent that. This form only covers the subsection's own fields plus
    new uploads.
    """

    images_upload = MultipleFileField(
        required=False,
        label="Add Images",
        help_text="Select one or more images (hold Ctrl/Cmd to multi-select). "
        "New uploads are added to the gallery below the existing images.",
    )

    class Meta:
        model = GallerySubsection
        fields = ["section", "title", "description", "sort_order", "is_published"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["section"].queryset = GallerySection.objects.all().order_by("sort_order", "title")
        self.fields["section"].empty_label = None
        self.fields["description"].required = False
        self.fields["is_published"].required = False
        self.fields["sort_order"].required = False
        self.order_fields(
            ["section", "title", "description", "sort_order", "is_published", "images_upload"]
        )
        self._style_fields()


class AdmissionInfoForm(TailwindStyledFormMixin, forms.ModelForm):
    """Used by admin.AdmissionInfoAdmin's custom add/change views."""

    image_upload = forms.ImageField(
        required=False,
        label="Upload Image",
        help_text="Optional. Uploading a file replaces whatever is in Image URL below.",
    )

    class Meta:
        model = AdmissionInfo
        fields = ["title", "description", "image_url", "admission_fee", "monthly_fee", "duration", "is_active"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 5}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["description"].required = False
        self.fields["admission_fee"].required = False
        self.fields["monthly_fee"].required = False
        self.fields["duration"].required = False
        self.fields["is_active"].required = False
        self.fields["image_url"].required = False
        self.fields["image_url"].label = "Image URL (or paste a link instead)"
        self.fields["image_url"].widget = forms.TextInput(attrs={"placeholder": "https://..."})
        self.order_fields(
            ["title", "description", "image_upload", "image_url", "admission_fee", "monthly_fee", "duration", "is_active"]
        )
        self._style_fields()

    def save(self, commit=True):
        instance = super().save(commit=False)
        uploaded = self.cleaned_data.get("image_upload")
        if uploaded:
            from django.core.files.storage import default_storage

            path = default_storage.save(f"admission/{uploaded.name}", uploaded)
            instance.image_url = default_storage.url(path)
        if commit:
            instance.save()
        return instance


class AdmissionInquiryAdminForm(TailwindStyledFormMixin, forms.ModelForm):
    """
    Used by admin.AdmissionInquiryAdmin's custom add/change views.

    This is deliberately separate from AdmissionInquiryForm (the public
    admission page's form): that one has the honeypot and no status
    field, since visitors don't set their own inquiry status; this one
    is for staff triaging inquiries from the dashboard.
    """

    class Meta:
        model = AdmissionInquiry
        fields = [
            "student_name",
            "student_phone",
            "guardian_name",
            "guardian_phone",
            "class_obj",
            "message",
            "status",
        ]
        labels = {
            "class_obj": "Class applying for",
        }
        widgets = {
            "message": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["guardian_name"].required = False
        self.fields["guardian_phone"].required = False
        self.fields["message"].required = False
        self.fields["class_obj"].required = False
        self.fields["class_obj"].empty_label = "Select a class"
        self._style_fields()


class ContactMessageAdminForm(TailwindStyledFormMixin, forms.ModelForm):
    """
    Used by admin.ContactMessageAdmin's custom add/change views.

    Separate from ContactMessageForm (the public contact page's form)
    for the same reason as AdmissionInquiryAdminForm — no honeypot, but
    it does have a status field for staff to update.
    """

    class Meta:
        model = ContactMessage
        fields = ["name", "phone", "email", "message", "status"]
        widgets = {
            "message": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["phone"].required = False
        self.fields["email"].required = False
        self._style_fields()

    def clean(self):
        cleaned_data = super().clean()
        phone = cleaned_data.get("phone")
        email = cleaned_data.get("email")
        # Same rule as the public-facing form — staff need some way to
        # reply, so don't let both be cleared out.
        if not phone and not email:
            raise ValidationError(
                "Please provide a phone number or an email so there's a way to reply."
            )
        return cleaned_data