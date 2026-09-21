"""Replace the ISPSC Extension Agenda (home thrust cards) with the current list.

The wizard checklist in ``proposals.views.constants.THRUST_LIST`` is the same
eight items. Existing proposal selections keep whatever name was saved; only
the chips offered from this point on, and the public Home cards, change.
"""

from django.db import migrations


AGENDA = [
    (
        "Sustainable Community Development and Livelihood Enhancement",
        "Community-based livelihood programs that strengthen local economies and sustainable development.",
        "text-green-600",
    ),
    (
        "Agriculture, Fisheries, and Food Security Extension",
        "Extension support for farming, fisheries, and food-secure communities.",
        "text-lime-600",
    ),
    (
        "Environmental Conservation and Climate Resilience",
        "Conservation programs and climate-resilient practices for communities and ecosystems.",
        "text-blue-600",
    ),
    (
        "Education, Literacy, and Human Resource Development",
        "Literacy, education, and capacity-building for people and institutions.",
        "text-purple-600",
    ),
    (
        "Health, Nutrition, and Wellness Promotion",
        "Health promotion, nutrition education, and wellness outreach.",
        "text-cyan-600",
    ),
    (
        "Technology Transfer and Innovation Extension",
        "Dissemination of research, technology, and innovation to partner communities.",
        "text-teal-600",
    ),
    (
        "Governance, Policy Advocacy, and Institutional Partnership",
        "Policy advocacy, governance capacity, and partnerships with institutions.",
        "text-red-600",
    ),
    (
        "Cultural Preservation and Social Inclusion",
        "Safeguarding cultural heritage and promoting inclusive participation.",
        "text-violet-600",
    ),
]


def replace_agenda(apps, schema_editor):
    HomeThrust = apps.get_model("details", "HomeThrust")
    HomeThrust.objects.all().delete()
    for index, (title, description, color) in enumerate(AGENDA, start=1):
        HomeThrust.objects.create(
            title=title,
            description=description,
            color_class=color,
            order=index,
            is_visible=True,
        )


def restore_previous(apps, schema_editor):
    HomeThrust = apps.get_model("details", "HomeThrust")
    HomeThrust.objects.all().delete()
    previous = [
        ("Indigenous Heritage Protection", "Protecting cultural heritage and indigenous rights within community extension activities.", "text-green-600"),
        ("Environmental Protection", "Programs that conserve ecosystems and promote sustainable practices.", "text-blue-600"),
        ("Resource Sharing", "Facilitating equitable distribution and community access to resources.", "text-yellow-500"),
        ("Numeracy and Literacy", "Adult and community education initiatives to improve literacy and numeracy.", "text-purple-600"),
        ("Governance and Administration", "Capacity-building and systems strengthening for local governance and administration.", "text-red-600"),
        ("IP-TBM Office Establishment", "Setting up institutional structures for technology-business management and IP.", "text-indigo-600"),
        ("Trade Fair and Exhibit", "Showcasing local products and linking producers to markets.", "text-pink-500"),
        ("Technology Transfer & RD Results Dissemination", "Dissemination of research outputs and support for technology uptake.", "text-teal-600"),
        ("Network and Linkage", "Building partnerships, MOUs, and collaborative networks.", "text-orange-500"),
        ("Adult Education", "Lifelong learning programs and vocational upskilling for adults.", "text-lime-600"),
        ("Calamity & Disaster Rehabilitation", "Relief operations, rehabilitation, and disaster risk reduction activities.", "text-rose-500"),
        ("Entrepreneurship & Financial Literacy", "Microenterprise support, financial literacy trainings, and market linkages.", "text-amber-500"),
        ("Health and Nutrition", "Health promotion, nutrition education, and preventive care outreach.", "text-cyan-600"),
        ("Advocacies & Social Justice", "Community advocacy, rights awareness, and social justice initiatives.", "text-violet-600"),
    ]
    for index, (title, description, color) in enumerate(previous, start=1):
        HomeThrust.objects.create(
            title=title,
            description=description,
            color_class=color,
            order=index,
            is_visible=True,
        )


class Migration(migrations.Migration):

    dependencies = [
        ("details", "0029_gender_issue_step_description"),
    ]

    operations = [
        migrations.RunPython(replace_agenda, restore_previous),
    ]
