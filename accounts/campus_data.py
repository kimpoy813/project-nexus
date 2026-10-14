# accounts/campus_data.py

CAMPUS_STRUCTURE = {
    "Candon": {
        "College of Hospitality and Tourism": [
            "Bachelor of Science in Hospitality Management",
            "Bachelor of Science in Tourism Management",
        ],
        "": [
            "Bachelor of Science in Information Technology",
            "Bachelor of Secondary Education",
        ],
    },
    "Main": {
        "College of Arts and Sciences": [
            "Bachelor of Arts in English Language",
            "Bachelor of Arts in Political Science",
            "Bachelor of Science in Computer Science",
        ],
        "College of Business Management & Entrepreneurship": [
            "Bachelor of Science in Business Administration",
            "Bachelor of Science in Office Administration",
        ],
        "Collge of Teacher Education": [
            "Bachelor of Secondary Education",
            "Bachelor of Elementary Education",
            "Bachelor of Physical Education",
            "Bachelor of Culture and Arts Education",
        ],
        "School of Criminal Justice Education": [
            "Bachelor of Science in Criminology",
        ],
        "College of Health Sciences": [
            "Bachelor of Science in Midwifery",
            "Bachelor of Science in Nursing",
        ],
    },
    "Sta Maria": {
        "College of Teacher Education (CTE)": [
            "Bachelor of Elementary Education",
            "Bachelor of Secondary Education",
            "Bachelor of Technology and Livelihood Education",
        ],
        "College of Computing Studies (CCS)": [
            "Bachelor of Science in Information Technology",
            "Bachelor of Science in Information Systems",
        ],
        "College of Agriculture, Forestry, Engineering, & Development Communication (CAFEDC)": [
            "Bachelor of Science in Agriculture",
            "Bachelor of Science in Forestry",
            "Bachelor of Science in Agroforestry",
            "Bachelor of Science in Agricultural and Biosystems Engineering",
            "Bachelor of Science in Development Communication",
        ],
        "College of Business Management and Entreprenership CBME)": [
            "Bachelor of Science in Hospitality Management",
        ],
        "College of Graduate Studies (CGS)": [
            "Doctor of Education in Educational Management",
            "Doctor of Philosophy in English Language Education",
            "Doctor of Philosophy in Agronomy",
            "Doctor of Philosophy in Technology Education Management",
            "Master of Arts in Education",
        ],
    },
    "Cervantes": {
        "": [
            "Bachelor of Elementary Education",
            "Bachelor of Secondary Education",
            "Bachelor of Science in Information Technology",
            "Bachelor of Science in Criminology",
            "Bachelor of Technology and Livelihood Education",
            "Bachelor of Technical-Vocational Teacher Education",
        ],
    },
    "Tagudin": {
        "College of Teacher Education (CTE)": [
            "Bachelor of Secondary Education",
            "Bachelor of Elementary Education",
            "Bachelor of Physical Education",
        ],
        "College of Arts and Sciences (CAS)": [
            "Bachelor of Arts in Psychology",
            "Bachelor of Arts in Social Science",
            "Bachelor of Science in Mathematics",
            "Bachelor of Science in Information Technology",
            "Bachelor of Arts in English Language",
            "Bachelor of Public Administration",
        ],
        "College of Business Management and Entrepreneurship (CBME)": [
            "Bachelor of Science in Business Administration",
            "Bachelor of Science in Entrepreneurship",
        ],
    },
    "Narvacan": {
        "": [
            "Bachelor of Science in Fisheries",
            "Bachelor of Technology and Livelihood Education",
            "Bachelor of Physical Education",
        ],
    },
    "Santiago": {
        "Institute of Technology": [
            "Bachelor of Science in Industrial Technology",
            "Bachelor of Science in Mechatronics Technology",
        ],
        "College of Teacher Education": [
            "Bachelor of Technical Vocation Teacher Education",
        ],
    },
}


# Historical seed data above is retained for migrations. Runtime choices come
# exclusively from the managed tables: deleting a row must not resurrect it.
import logging
from django.apps import apps
from django.db import DatabaseError
from django.db.models import Q

logger = logging.getLogger(__name__)


def _choices(query):
    try:
        return [(value, value) for value in query.values_list("name", flat=True).order_by("name") if value]
    except DatabaseError:
        logger.warning("Organizational choices are unavailable.", exc_info=True)
        return []


def get_campus_choices():
    return _choices(apps.get_model("accounts", "Campus").objects.all())


def get_college_choices(campus=None):
    if not campus:
        return []
    return _choices(apps.get_model("accounts", "College").objects.filter(campus__name=campus))


def get_department_choices(campus=None, college=None):
    if not campus:
        return []
    query = apps.get_model("accounts", "Department").objects.filter(campus__name=campus)
    if college:
        query = query.filter(college__name=college)
    else:
        query = query.filter(Q(college__isnull=True) | Q(college__name=""))
    return _choices(query)


def is_valid_college_for_campus(campus, college):
    return not college or (college, college) in get_college_choices(campus)


def is_valid_department_for_selection(campus, college, department):
    return not department or (department, department) in get_department_choices(campus, college)
