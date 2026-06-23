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


def get_campus_choices():
    return [(campus, campus) for campus in CAMPUS_STRUCTURE.keys()]


def get_college_choices(campus=None):
    if not campus or campus not in CAMPUS_STRUCTURE:
        return []

    choices = []
    for college in CAMPUS_STRUCTURE[campus].keys():
        if college:
            choices.append((college, college))
    return choices


def get_department_choices(campus=None, college=None):
    if not campus or campus not in CAMPUS_STRUCTURE:
        return []

    departments = []

    if college is None:
        college = ""

    if college in CAMPUS_STRUCTURE[campus]:
        departments.extend(CAMPUS_STRUCTURE[campus][college])

    return [(dept, dept) for dept in departments]


def is_valid_college_for_campus(campus, college):
    if not college:
        return True
    return campus in CAMPUS_STRUCTURE and college in CAMPUS_STRUCTURE[campus]


def is_valid_department_for_selection(campus, college, department):
    if not department:
        return True

    if campus not in CAMPUS_STRUCTURE:
        return False

    college = college or ""
    allowed = CAMPUS_STRUCTURE[campus].get(college, [])
    return department in allowed