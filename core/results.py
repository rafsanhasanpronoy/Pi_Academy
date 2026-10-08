"""
Grading and exam-report helpers, shared by everything that shows results
(the admin student page, the public results lookup, the bulk upload) so
they can never disagree with each other.

The scale below is the standard Bangladesh GPA scale (SSC/HSC style):
percentage of full marks -> letter grade -> grade point. If the academy
grades differently, change GRADE_SCALE / PASS_PERCENT here and every
page and upload follows.
"""
from decimal import Decimal, ROUND_HALF_UP

# A subject is failed below this percentage of full marks.
PASS_PERCENT = Decimal("33")

# (minimum percentage, letter grade, grade point) — highest first.
GRADE_SCALE = [
    (Decimal("80"), "A+", Decimal("5.00")),
    (Decimal("70"), "A", Decimal("4.00")),
    (Decimal("60"), "A-", Decimal("3.50")),
    (Decimal("50"), "B", Decimal("3.00")),
    (Decimal("40"), "C", Decimal("2.00")),
    (Decimal("33"), "D", Decimal("1.00")),
    (Decimal("0"), "F", Decimal("0.00")),
]
_POINT_BY_GRADE = {grade: point for _min, grade, point in GRADE_SCALE}

DEFAULT_FULL_MARKS = Decimal("100")
_TWO_PLACES = Decimal("0.01")


def _dec(value, default=Decimal("0")):
    if value is None:
        return default
    return value if isinstance(value, Decimal) else Decimal(str(value))


def percentage(marks, full_marks):
    """Marks as a percentage of full marks (0 if full marks is unusable)."""
    full = _dec(full_marks, DEFAULT_FULL_MARKS)
    if full <= 0:
        return Decimal("0")
    return (_dec(marks) * 100 / full)


def grade_for(marks, full_marks):
    """-> (letter grade, grade point) for marks out of full_marks."""
    pct = percentage(marks, full_marks)
    for minimum, grade, point in GRADE_SCALE:
        if pct >= minimum:
            return grade, point
    return "F", Decimal("0.00")


def grade_for_gpa(gpa):
    """Overall letter grade for a GPA (5.00 -> A+ ... below 1 -> F)."""
    gpa = _dec(gpa)
    for _minimum, grade, point in GRADE_SCALE:
        if gpa >= point:
            return grade
    return "F"


def is_pass(marks, full_marks):
    return percentage(marks, full_marks) >= PASS_PERCENT


def _quantize(value):
    return _dec(value).quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)


def build_exam_report(exam, results):
    """
    One exam's results for one student, ready to display.

    GPA follows the usual Bangladesh rule: the average of the subjects'
    grade points, but 0.00 (and an overall F) if ANY subject is failed.
    A grade typed in by hand is respected (its point comes from the scale)
    so a moderated grade isn't silently overridden in the totals.
    """
    full_marks = _dec(getattr(exam, "full_marks", None), DEFAULT_FULL_MARKS)
    rows = []
    total = Decimal("0")
    points = Decimal("0")
    any_failed = False

    ordered = sorted(results, key=lambda r: r.subject.subject_name.lower())
    for result in ordered:
        computed_grade, computed_point = grade_for(result.marks, full_marks)
        grade = result.grade if result.grade in _POINT_BY_GRADE else computed_grade
        point = _POINT_BY_GRADE.get(grade, computed_point)
        passed = is_pass(result.marks, full_marks) and grade != "F"
        any_failed = any_failed or not passed
        total += _dec(result.marks)
        points += point
        rows.append({
            "result": result,
            "subject": result.subject.subject_name,
            "marks": result.marks,
            "full_marks": full_marks,
            "grade": grade,
            "grade_point": point,
            "passed": passed,
        })

    count = len(rows)
    full_total = full_marks * count
    gpa = Decimal("0.00") if (any_failed or not count) else _quantize(points / count)
    return {
        "exam": exam,
        "rows": rows,
        "subject_count": count,
        "total": total,
        "full_total": full_total,
        "percentage": _quantize(total * 100 / full_total) if full_total else Decimal("0.00"),
        "gpa": gpa,
        "overall_grade": grade_for_gpa(gpa) if count else "",
        "passed": bool(count) and not any_failed,
    }


def reports_for_student(student):
    """All of a student's exams, newest first, as build_exam_report dicts."""
    from .models import ExamResult  # local import: models imports nothing from here

    results = (
        ExamResult.objects.filter(student=student)
        .select_related("exam", "subject")
        .order_by("-exam__exam_date", "-exam_id")
    )
    grouped = {}
    for result in results:
        grouped.setdefault(result.exam_id, (result.exam, []))[1].append(result)
    return [build_exam_report(exam, rows) for exam, rows in grouped.values()]