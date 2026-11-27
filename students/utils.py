
import re
from .models import Student


def generate_admission_number():
    """
    Generate the next official Fastline admission number.
    Format: FHI000001, FHI000002, FHI000003...
    """
    existing_numbers = Student.objects.filter(
        registration_number__startswith="FHI"
    ).values_list("registration_number", flat=True)

    highest_number = 0

    for number in existing_numbers:
        match = re.fullmatch(r"FHI(\d+)", number)
        if match:
            highest_number = max(highest_number, int(match.group(1)))

    return f"FHI{highest_number + 1:06d}"
