from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import F, Prefetch
from django.shortcuts import redirect, render

# pip install django-ratelimit
from django_ratelimit.decorators import ratelimit

from .forms import AdmissionInquiryForm, ContactMessageForm, StudentLookupForm
from .models import (
    Achievement,
    AdmissionInfo,
    Attendance,
    Batch,
    Class,
    ClassSchedule,
    ExamResult,
    Faculty,
    GallerySection,
    GallerySubsection,
    Notice,
    Student,
)


def home(request):
    context = {
        "notices": Notice.objects.filter(is_published=True).order_by("-published_date")[:3],
        "achievements": Achievement.objects.filter(is_published=True)
        .order_by(F("achievement_date").desc(nulls_last=True))[:3],
        "admission_infos": AdmissionInfo.objects.filter(is_active=True)[:2],
    }
    return render(request, "core/home.html", context)


def about(request):
    return render(request, "core/about.html")


def admission(request):
    if request.method == "POST":
        form = AdmissionInquiryForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(
                request,
                "Your inquiry has been received. Our team will call you within 24 hours.",
            )
            return redirect("admission")
    else:
        form = AdmissionInquiryForm()

    context = {
        "form": form,
        "admission_infos": AdmissionInfo.objects.filter(is_active=True),
    }
    return render(request, "core/admission.html", context)


def notices_list(request):
    notices_qs = Notice.objects.filter(is_published=True).order_by("-published_date")
    paginator = Paginator(notices_qs, 20)
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(request, "core/notices.html", {"notices": page_obj, "page_obj": page_obj})


def gallery_list(request):
    sections = GallerySection.objects.filter(is_published=True).order_by("sort_order", "title").prefetch_related(
        Prefetch(
            "subsections",
            queryset=GallerySubsection.objects.filter(is_published=True).order_by("sort_order", "title"),
        )
    )
    return render(request, "core/gallery.html", {"sections": sections})


def achievements_list(request):
    achievements_qs = Achievement.objects.filter(is_published=True).order_by(
        F("achievement_date").desc(nulls_last=True)
    )
    paginator = Paginator(achievements_qs, 12)
    page_obj = paginator.get_page(request.GET.get("page"))
    for achievement in page_obj:
        achievement.gallery_images = achievement.image_urls or (
            [achievement.image_url] if achievement.image_url else []
        )
    return render(
        request, "core/achievements.html", {"achievements": page_obj, "page_obj": page_obj}
    )


def contact(request):
    if request.method == "POST":
        form = ContactMessageForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Your message has been sent. We'll get back to you soon.")
            return redirect("contact")
    else:
        form = ContactMessageForm()

    return render(request, "core/contact.html", {"form": form})


def faculty_list(request):
    faculty_members = Faculty.objects.all().order_by("full_name")
    schedules = ClassSchedule.objects.select_related("teacher", "subject")

    subjects_by_teacher = {}
    for sched in schedules:
        subjects_by_teacher.setdefault(sched.teacher_id, set()).add(sched.subject.subject_name)

    faculty_data = [
        {"faculty": f, "subjects": sorted(subjects_by_teacher.get(f.id, []))}
        for f in faculty_members
    ]
    return render(request, "core/faculty.html", {"faculty_data": faculty_data})


def classes_list(request):
    classes = Class.objects.prefetch_related("batch_set").order_by("-academic_year", "class_name")
    return render(request, "core/classes.html", {"classes": classes})


# 5 attempts per minute per IP, then blocked with a 429. This is the fix
# for the brute-force / enumeration risk on student lookup: without this,
# nothing stops an automated script from cycling through student codes
# and phone numbers to pull attendance + exam data.
@ratelimit(key="ip", rate="5/m", method="POST", block=True)
def student_results(request):
    context = {}
    if request.method == "POST":
        form = StudentLookupForm(request.POST)
        if form.is_valid():
            code = form.cleaned_data["student_code"].strip()
            phone = form.cleaned_data["student_phone"].strip()
            student = Student.objects.filter(
                student_code__iexact=code, student_phone=phone
            ).first()

            if student:
                results_qs = (
                    ExamResult.objects.filter(student=student)
                    .select_related("exam", "subject")
                    .order_by("-exam__exam_date")
                )
                exams = {}
                for result in results_qs:
                    exams.setdefault(result.exam, []).append(result)

                attendance_qs = Attendance.objects.filter(student=student)
                attendance_summary = {
                    "total": attendance_qs.count(),
                    "present": attendance_qs.filter(status="Present").count(),
                    "absent": attendance_qs.filter(status="Absent").count(),
                    "late": attendance_qs.filter(status="Late").count(),
                }

                context.update({
                    "student": student,
                    "exams": exams,
                    "attendance_summary": attendance_summary,
                    "recent_attendance": attendance_qs.order_by("-attendance_date")[:10],
                    "searched": True,
                })
            else:
                context["not_found"] = True
    else:
        form = StudentLookupForm()

    context["form"] = form
    return render(request, "core/results.html", context)