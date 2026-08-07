from django.test import TestCase
from django.core.exceptions import ValidationError
from django.apps import apps
from accounts.models import Campus, College, Department
from accounts.campus_data import (
    get_campus_choices,
    get_college_choices,
    get_department_choices,
    is_valid_college_for_campus,
    is_valid_department_for_selection,
)
from accounts.forms import RegisterForm


class DynamicChoicesTestCase(TestCase):
    def setUp(self):
        # Clear existing to start with empty db for some fallback testing,
        # although migrations already run and populate them.
        Department.objects.all().delete()
        College.objects.all().delete()
        Campus.objects.all().delete()

    def test_fallback_choices(self):
        """When database is empty, it should fall back to CAMPUS_STRUCTURE keys."""
        campuses = get_campus_choices()
        self.assertIn(("Candon", "Candon"), campuses)
        self.assertIn(("Main", "Main"), campuses)

        colleges = get_college_choices("Candon")
        self.assertIn(
            ("College of Hospitality and Tourism", "College of Hospitality and Tourism"),
            colleges
        )

        departments = get_department_choices("Candon", "College of Hospitality and Tourism")
        self.assertIn(
            ("Bachelor of Science in Hospitality Management", "Bachelor of Science in Hospitality Management"),
            departments
        )

    def test_database_backed_choices(self):
        """When database is populated, choices must be fetched from the database."""
        campus = Campus.objects.create(name="Virtual Campus")
        college = College.objects.create(campus=campus, name="School of Coding")
        dept = Department.objects.create(campus=campus, college=college, name="AI Engineering")

        campuses = get_campus_choices()
        # Since database is populated, it should return database values only
        self.assertEqual(campuses, [("Virtual Campus", "Virtual Campus")])

        colleges = get_college_choices("Virtual Campus")
        self.assertEqual(colleges, [("School of Coding", "School of Coding")])

        departments = get_department_choices("Virtual Campus", "School of Coding")
        self.assertEqual(departments, [("AI Engineering", "AI Engineering")])

    def test_is_valid_helpers(self):
        """Validation helpers should look at the database first."""
        campus = Campus.objects.create(name="Sograts Campus")
        college = College.objects.create(campus=campus, name="School of Wisdom")
        Department.objects.create(campus=campus, college=college, name="Philosophy")

        self.assertTrue(is_valid_college_for_campus("Sograts Campus", "School of Wisdom"))
        self.assertFalse(is_valid_college_for_campus("Sograts Campus", "School of Lies"))

        self.assertTrue(is_valid_department_for_selection("Sograts Campus", "School of Wisdom", "Philosophy"))
        self.assertFalse(is_valid_department_for_selection("Sograts Campus", "School of Wisdom", "Theology"))

    def test_register_form_validation_with_db_values(self):
        """RegisterForm must successfully setup and validate choices with database-backed values."""
        campus = Campus.objects.create(name="Cyber Campus")
        college = College.objects.create(campus=campus, name="Institute of Hacking")
        dept = Department.objects.create(campus=campus, college=college, name="Ethical Hacking")

        # Let's instantiate form with data
        data = {
            "full_name": "Test User",
            "username": "testuser",
            "email": "tester@example.com",
            "campus": "Cyber Campus",
            "college": "Institute of Hacking",
            "department": "Ethical Hacking",
            "password": "ValidPass123!@#",
            "confirm_password": "ValidPass123!@#",
        }
        form = RegisterForm(data=data)
        # Call setup_dependent_choices explicitly or through init
        form.setup_dependent_choices()
        
        # Verify choices in form fields are correctly loaded
        self.assertIn(("Cyber Campus", "Cyber Campus"), form.fields["campus"].choices)
        self.assertIn(("Institute of Hacking", "Institute of Hacking"), form.fields["college"].choices)
        self.assertIn(("Ethical Hacking", "Ethical Hacking"), form.fields["department"].choices)
        
        # Clean should be valid
        self.assertTrue(form.is_valid(), form.errors)
