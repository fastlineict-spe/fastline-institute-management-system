from django.db import migrations


def create_campuses(apps, schema_editor):
    Campus = apps.get_model("accounts", "Campus")

    Campus.objects.using(schema_editor.connection.alias).update_or_create(
        code="NAMUGONGO",
        defaults={
            "name": "Namugongo Campus",
            "phone_primary": "",
            "phone_secondary": "",
            "is_command_centre": True,
            "is_active": True,
        },
    )

    Campus.objects.using(schema_editor.connection.alias).update_or_create(
        code="BUSIA",
        defaults={
            "name": "Busia Campus",
            "phone_primary": "",
            "phone_secondary": "",
            "is_command_centre": False,
            "is_active": True,
        },
    )


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0002_campus_user_is_central_admin_user_campus"),
    ]

    operations = [
        migrations.RunPython(
            create_campuses,
            migrations.RunPython.noop,
        ),
    ]
