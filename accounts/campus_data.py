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


def structure_dict_to_json(structure=None):
    """Convert the legacy nested dict into the editable institution JSON shape."""
    source = structure or CAMPUS_STRUCTURE
    return {
        "campuses": [
            {
                "name": campus,
                "colleges": [
                    {
                        "name": college,
                        "departments": list(departments or []),
                    }
                    for college, departments in colleges.items()
                ],
            }
            for campus, colleges in source.items()
        ]
    }


def structure_json_to_dict(structure):
    """Normalize an institution JSON structure into {campus: {college: [departments]}}."""
    campuses = (structure or {}).get("campuses") or []
    normalized = {}
    for campus_row in campuses:
        campus_name = (campus_row.get("name") or "").strip()
        if not campus_name:
            continue

        colleges = {}
        for college_row in campus_row.get("colleges") or []:
            college_name = (college_row.get("name") or "").strip()
            departments = []
            for department in college_row.get("departments") or []:
                department_name = (department or "").strip()
                if department_name and department_name not in departments:
                    departments.append(department_name)
            colleges[college_name] = departments

        if not colleges:
            colleges[""] = []
        normalized[campus_name] = colleges
    return normalized


def get_structure_for_institution(institution=None):
    if institution is not None:
        structure = getattr(institution, "structure", None)
        normalized = structure_json_to_dict(structure)
        if normalized:
            return normalized
    return CAMPUS_STRUCTURE


def get_default_structure_json():
    return structure_dict_to_json(CAMPUS_STRUCTURE)


def get_campus_choices(institution=None):
    structure = get_structure_for_institution(institution)
    return [(campus, campus) for campus in structure.keys()]


def get_college_choices(campus=None, institution=None):
    structure = get_structure_for_institution(institution)
    if not campus or campus not in structure:
        return []

    choices = []
    for college in structure[campus].keys():
        if college:
            choices.append((college, college))
    return choices


def get_department_choices(campus=None, college=None, institution=None):
    structure = get_structure_for_institution(institution)
    if not campus or campus not in structure:
        return []

    departments = []

    if college is None:
        college = ""

    if college in structure[campus]:
        departments.extend(structure[campus][college])

    return [(dept, dept) for dept in departments]


def is_valid_college_for_campus(campus, college, institution=None):
    if not college:
        return True
    structure = get_structure_for_institution(institution)
    return campus in structure and college in structure[campus]


def is_valid_department_for_selection(campus, college, department, institution=None):
    if not department:
        return True

    structure = get_structure_for_institution(institution)

    if campus not in structure:
        return False

    college = college or ""
    allowed = structure[campus].get(college, [])
    return department in allowed