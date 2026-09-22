# This is an auto-generated Django model module.
# You'll have to do the following manually to clean this up:
#   * Rearrange models' order
#   * Make sure each model has one field with primary_key=True
#   * Make sure each ForeignKey and OneToOneField has `on_delete` set to the desired behavior
#   * Remove `managed = False` lines if you wish to allow Django to create, modify, and delete the table
# Feel free to rename the models, but don't rename db_table values or field names.
import django
from django.core.validators import MinValueValidator
from django.db import models

# CompositePrimaryKey was added in Django 5.2. If you're on an older
# version this import (and therefore the whole app) fails at startup —
# so we detect the version instead of assuming it's available.
DJANGO_VERSION = django.VERSION[:2]
_HAS_COMPOSITE_PK = DJANGO_VERSION >= (5, 2)


class Achievement(models.Model):
    id = models.BigAutoField(primary_key=True)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    image_url = models.TextField(blank=True, null=True)
    image_urls = models.JSONField(default=list, blank=True)
    achievement_date = models.DateField(blank=True, null=True)
    is_published = models.BooleanField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = 'achievements'

    def __str__(self):
        return self.title


class AdmissionInfo(models.Model):
    id = models.BigAutoField(primary_key=True)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    image_url = models.TextField(blank=True, null=True)
    admission_fee = models.DecimalField(
        max_digits=10, decimal_places=2, blank=True, null=True,
        validators=[MinValueValidator(0)],
    )
    monthly_fee = models.DecimalField(
        max_digits=10, decimal_places=2, blank=True, null=True,
        validators=[MinValueValidator(0)],
    )
    duration = models.CharField(max_length=100, blank=True, null=True)
    is_active = models.BooleanField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = 'admission_info'

    def __str__(self):
        return self.title


class AdmissionInquiry(models.Model):
    id = models.BigAutoField(primary_key=True)
    student_name = models.CharField(max_length=150)
    student_phone = models.CharField(max_length=20)
    guardian_name = models.CharField(max_length=150, blank=True, null=True)
    guardian_phone = models.CharField(max_length=20, blank=True, null=True)
    class_obj = models.ForeignKey('Class', models.DO_NOTHING, db_column='class_id', blank=True, null=True)
    message = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=[
        ('New', 'New'),
        ('Contacted', 'Contacted'),
        ('Admitted', 'Admitted'),
        ('Rejected', 'Rejected'),
    ], default='New')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = 'admission_inquiries'
        verbose_name = 'Admission Inquiry'
        verbose_name_plural = 'Admission Inquiries'

    def __str__(self):
        return self.student_name


class Attendance(models.Model):
    id = models.BigAutoField(primary_key=True)
    student = models.ForeignKey('Student', models.DO_NOTHING)
    batch = models.ForeignKey('Batch', models.DO_NOTHING)
    attendance_date = models.DateField()
    status = models.CharField(max_length=20, choices=[
        ('Present', 'Present'),
        ('Absent', 'Absent'),
        ('Late', 'Late'),
    ])
    remarks = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'attendance'
        # NOTE (flagged in QA pass): this constrains a student to ONE
        # attendance record per day system-wide, even though `batch` is
        # also stored on this row. If a student can ever be in more than
        # one batch, change this to unique_together on
        # (student, batch, attendance_date) instead — confirm the
        # intended business rule before changing, since it affects
        # existing data.
        unique_together = (('student', 'attendance_date'),)
        verbose_name = 'Attendance Record'
        verbose_name_plural = 'Attendance Records'

    def __str__(self):
        return f"{self.student} — {self.attendance_date} ({self.status})"


class Batch(models.Model):
    id = models.BigAutoField(primary_key=True)
    class_obj = models.ForeignKey('Class', models.DO_NOTHING, db_column='class_id')
    batch_name = models.CharField(max_length=100)
    room = models.CharField(max_length=50, blank=True, null=True)
    start_time = models.TimeField(blank=True, null=True)
    end_time = models.TimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'batches'
        unique_together = (('class_obj', 'batch_name'),)
        verbose_name = 'Batch'
        verbose_name_plural = 'Batches'

    def __str__(self):
        return f"{self.class_obj.class_name} — {self.batch_name}"


class ClassSchedule(models.Model):
    id = models.BigAutoField(primary_key=True)
    class_obj = models.ForeignKey('Class', models.DO_NOTHING, db_column='class_id')
    batch = models.ForeignKey(Batch, models.DO_NOTHING)
    teacher = models.ForeignKey('Faculty', models.DO_NOTHING)
    subject = models.ForeignKey('Subject', models.DO_NOTHING)
    day_of_week = models.CharField(max_length=20)
    start_time = models.TimeField()
    end_time = models.TimeField()
    room = models.CharField(max_length=50, blank=True, null=True)
    status = models.CharField(max_length=20, choices=[
        ('Active', 'Active'),
        ('Cancelled', 'Cancelled'),
        ('Rescheduled', 'Rescheduled'),
    ], default='Active')
    notes = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'class_schedule'

    def __str__(self):
        return f"{self.batch} — {self.subject} ({self.day_of_week})"


class Class(models.Model):
    id = models.BigAutoField(primary_key=True)
    class_name = models.CharField(max_length=100)
    academic_year = models.IntegerField()

    class Meta:
        managed = False
        db_table = 'classes'
        unique_together = (('class_name', 'academic_year'),)
        verbose_name = 'Class'
        verbose_name_plural = 'Classes'

    def __str__(self):
        return f"{self.class_name} ({self.academic_year})"


class ContactMessage(models.Model):
    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=150)
    phone = models.CharField(max_length=20, blank=True, null=True)
    email = models.CharField(max_length=150, blank=True, null=True)
    message = models.TextField()
    status = models.CharField(max_length=20, choices=[
        ('Unread', 'Unread'),
        ('Read', 'Read'),
        ('Replied', 'Replied'),
    ], default='Unread')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = 'contact_messages'

    def __str__(self):
        return self.name


class ExamResult(models.Model):
    id = models.BigAutoField(primary_key=True)
    exam = models.ForeignKey('Exam', models.DO_NOTHING)
    student = models.ForeignKey('Student', models.DO_NOTHING)
    subject = models.ForeignKey('Subject', models.DO_NOTHING)
    marks = models.DecimalField(max_digits=5, decimal_places=2, validators=[MinValueValidator(0)])
    grade = models.CharField(max_length=10, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'exam_results'
        unique_together = (('exam', 'student', 'subject'),)

    def __str__(self):
        return f"{self.student} — {self.subject} ({self.marks})"


class Exam(models.Model):
    id = models.BigAutoField(primary_key=True)
    class_obj = models.ForeignKey(Class, models.DO_NOTHING, db_column='class_id')
    exam_name = models.CharField(max_length=100)
    exam_date = models.DateField()

    class Meta:
        managed = False
        db_table = 'exams'

    def __str__(self):
        return f"{self.exam_name} — {self.class_obj.class_name}"


class Faculty(models.Model):
    id = models.BigAutoField(primary_key=True)
    full_name = models.CharField(max_length=150)
    photo_url = models.TextField(blank=True, null=True)
    designation = models.CharField(max_length=100, blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    email = models.CharField(max_length=150, blank=True, null=True)
    joining_date = models.DateField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = 'faculty'
        verbose_name = 'Faculty'
        verbose_name_plural = 'Faculty'

    def __str__(self):
        return self.full_name


class Gallery(models.Model):
    id = models.BigAutoField(primary_key=True)
    title = models.CharField(max_length=200, blank=True, null=True)
    image_url = models.TextField()
    category = models.CharField(max_length=100, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    is_published = models.BooleanField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = 'gallery'
        verbose_name = 'Gallery Item'
        verbose_name_plural = 'Gallery Items'

    def __str__(self):
        return self.title or f"Gallery item #{self.pk}"


class GallerySection(models.Model):
    """A top-level heading on the public Gallery page, e.g. 'Sports Day
    2026' or 'Campus'. Holds one or more GallerySubsections."""

    id = models.BigAutoField(primary_key=True)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    is_published = models.BooleanField(default=True)
    sort_order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = 'gallery_sections'
        verbose_name = 'Gallery Section'
        verbose_name_plural = 'Gallery Sections'

    def __str__(self):
        return self.title


class GallerySubsection(models.Model):
    """A group of images within a GallerySection, e.g. 'Day 1' or
    'Prize Giving'. `images` holds the gallery itself: a JSON list of
    {"url": ..., "description": ...} objects, each editable and
    individually removable from the admin."""

    id = models.BigAutoField(primary_key=True)
    section = models.ForeignKey(
        GallerySection,
        on_delete=models.CASCADE,
        related_name='subsections',
        db_column='section_id',
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    images = models.JSONField(default=list, blank=True)
    is_published = models.BooleanField(default=True)
    sort_order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = 'gallery_subsections'
        verbose_name = 'Gallery Subsection'
        verbose_name_plural = 'Gallery Subsections'

    def __str__(self):
        return self.title


class Notice(models.Model):
    id = models.BigAutoField(primary_key=True)
    title = models.CharField(max_length=200)
    description = models.TextField()
    image_url = models.TextField(blank=True, null=True)
    published_date = models.DateField()
    is_published = models.BooleanField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = 'notices'

    def __str__(self):
        return self.title


class StudentPayment(models.Model):
    id = models.BigAutoField(primary_key=True)
    student = models.ForeignKey('Student', models.DO_NOTHING)
    payment_type = models.CharField(max_length=30, choices=[
        ('Admission Fee', 'Admission Fee'),
        ('Monthly Fee', 'Monthly Fee'),
        ('Exam Fee', 'Exam Fee'),
        ('Registration Fee', 'Registration Fee'),
        ('Other', 'Other'),
    ])
    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    payment_date = models.DateField()
    payment_month = models.DateField(blank=True, null=True)
    remarks = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'student_payments'

    def __str__(self):
        return f"{self.student} — {self.payment_type} ({self.amount})"


class Student(models.Model):
    id = models.BigAutoField(primary_key=True)
    student_code = models.CharField(unique=True, max_length=30)
    class_obj = models.ForeignKey(Class, models.DO_NOTHING, db_column='class_id')
    batch = models.ForeignKey(Batch, models.DO_NOTHING, blank=True, null=True)
    full_name = models.CharField(max_length=150)
    photo_url = models.TextField(blank=True, null=True)
    gender = models.CharField(max_length=20, blank=True, null=True)
    date_of_birth = models.DateField(blank=True, null=True)
    student_phone = models.CharField(max_length=20, blank=True, null=True)
    father_name = models.CharField(max_length=150, blank=True, null=True)
    father_phone = models.CharField(max_length=20, blank=True, null=True)
    mother_name = models.CharField(max_length=150, blank=True, null=True)
    mother_phone = models.CharField(max_length=20, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    admission_date = models.DateField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=[
        ('Active', 'Active'),
        ('Inactive', 'Inactive'),
        ('Completed', 'Completed'),
        ('Left', 'Left'),
    ], default='Active')

    class Meta:
        managed = False
        db_table = 'students'

    def __str__(self):
        return f"{self.full_name} ({self.student_code})"


class Subject(models.Model):
    id = models.BigAutoField(primary_key=True)
    class_obj = models.ForeignKey('Class', models.DO_NOTHING, db_column='class_id')
    subject_name = models.CharField(max_length=100)
    subject_code = models.CharField(unique=True, max_length=30, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = 'subjects'
        unique_together = (('subject_name', 'class_obj'),)

    def __str__(self):
        return f"{self.subject_name} ({self.class_obj.class_name})"


class TeacherSalary(models.Model):
    PAYMENT_METHODS = [
        ("Cash", "Cash"),
        ("Bank", "Bank Transfer"),
        ("Bkash", "bKash"),
        ("Nagad", "Nagad"),
    ]

    id = models.BigAutoField(primary_key=True)
    teacher = models.ForeignKey(Faculty, models.DO_NOTHING)
    salary_month = models.DateField()

    # Legacy flat amount, kept untouched for old records and any code
    # still reading it. New records keep it in sync with net_salary
    # (see TeacherSalaryForm.save) but it's no longer edited directly.
    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])

    receipt_number = models.CharField(max_length=50, unique=True, blank=True, null=True)

    gross_salary = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    bonus = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    # "Other" deductions only (manual, e.g. an advance) — attendance-based
    # deductions are tracked separately below so re-editing a record never
    # double-applies them.
    deduction = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    present_days = models.PositiveIntegerField(default=0, blank=True)
    absent_days = models.PositiveIntegerField(default=0, blank=True)
    late_days = models.PositiveIntegerField(default=0, blank=True)
    attendance_deduction = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    net_salary = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    paid_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    due_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS, default="Cash")
    transaction_id = models.CharField(max_length=100, blank=True, null=True)

    payment_date = models.DateField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=[
        ('Pending', 'Pending'),
        ('Partial', 'Partially Paid'),
        ('Paid', 'Paid'),
    ], default='Pending')
    remarks = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'teacher_salary'
        unique_together = (('teacher', 'salary_month'),)
        verbose_name = 'Teacher Salary'
        verbose_name_plural = 'Teacher Salaries'

    def __str__(self):
        return f"{self.teacher} — {self.salary_month}"


if _HAS_COMPOSITE_PK:
    class TeacherSubject(models.Model):
        pk = models.CompositePrimaryKey('teacher_id', 'subject_id')
        teacher = models.ForeignKey(Faculty, models.DO_NOTHING)
        subject = models.ForeignKey(Subject, models.DO_NOTHING)

        class Meta:
            managed = False
            db_table = 'teacher_subjects'

        def __str__(self):
            return f"{self.teacher} — {self.subject}"
else:
    # Fallback for Django < 5.2, where CompositePrimaryKey doesn't exist.
    # Adds a synthetic surrogate id and enforces the same uniqueness via
    # unique_together instead of a true composite PK. Swap back to the
    # CompositePrimaryKey version once you're on Django 5.2+.
    class TeacherSubject(models.Model):
        id = models.BigAutoField(primary_key=True)
        teacher = models.ForeignKey(Faculty, models.DO_NOTHING)
        subject = models.ForeignKey(Subject, models.DO_NOTHING)

        class Meta:
            managed = False
            db_table = 'teacher_subjects'
            unique_together = (('teacher', 'subject'),)

        def __str__(self):
            return f"{self.teacher} — {self.subject}"


class Users(models.Model):
    # NOTE (flagged in QA pass): this model isn't referenced anywhere in
    # admin.py or views.py — the admin's "Users" section actually uses
    # Django's built-in auth.User. Confirm whether this table is still
    # needed (e.g. synced from another auth system) or safe to remove.
    id = models.UUIDField(primary_key=True)
    full_name = models.CharField(max_length=100)
    role = models.CharField(max_length=20)
    phone = models.CharField(max_length=20, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = 'users'

    def __str__(self):
        return self.full_name