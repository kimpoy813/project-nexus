"""
Seed ``ProposalProponent.sort_order`` from the existing row order.

The wizard can now reorder proponents (the generated documents print them in
this order), so existing rows need a starting position. Using each row's
previous position - its id, which is the order every queryset used to return -
keeps existing proposals printing exactly as they did before.
"""

from django.db import migrations


def seed_sort_order(apps, schema_editor):
    ProposalProponent = apps.get_model("proposals", "ProposalProponent")

    current_proposal = None
    position = 0
    pending = []

    for proponent in ProposalProponent.objects.order_by("proposal_id", "id").iterator():
        if proponent.proposal_id != current_proposal:
            current_proposal = proponent.proposal_id
            position = 0
        position += 1
        proponent.sort_order = position
        pending.append(proponent)

        if len(pending) >= 500:
            ProposalProponent.objects.bulk_update(pending, ["sort_order"])
            pending = []

    if pending:
        ProposalProponent.objects.bulk_update(pending, ["sort_order"])


class Migration(migrations.Migration):

    dependencies = [
        ("proposals", "0045_alter_proposalproponent_options_and_more"),
    ]

    operations = [
        migrations.RunPython(seed_sort_order, migrations.RunPython.noop),
    ]
