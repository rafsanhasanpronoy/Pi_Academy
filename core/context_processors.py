from django.conf import settings


def academy_branding(request):
    """Makes ACADEMY_LOGO_URL and the 3 program banner URLs available in
    every template without each view having to pass them explicitly —
    used in the site header/footer, both printable receipts, and the
    homepage program slider. Empty string for any that aren't set yet."""
    return {
        "ACADEMY_LOGO_URL": settings.ACADEMY_LOGO_URL,
        "PROGRAM_MATH_IMAGE_URL": settings.PROGRAM_MATH_IMAGE_URL,
        "PROGRAM_SCIENCE_IMAGE_URL": settings.PROGRAM_SCIENCE_IMAGE_URL,
        "PROGRAM_KIDS_IMAGE_URL": settings.PROGRAM_KIDS_IMAGE_URL,
    }
