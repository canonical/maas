import django.contrib.auth.models
import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("auth", "0001_initial")]

    operations = [
        migrations.AlterModelManagers(
            name="group",
            managers=[("objects", django.contrib.auth.models.GroupManager())],
        ),
        migrations.AlterModelManagers(
            name="permission",
            managers=[
                ("objects", django.contrib.auth.models.PermissionManager())
            ],
        ),
        migrations.AlterModelManagers(
            name="user",
            managers=[("objects", django.contrib.auth.models.UserManager())],
        ),
        migrations.AlterField(
            model_name="permission",
            name="name",
            field=models.CharField(max_length=255, verbose_name="name"),
        ),
        migrations.AlterField(
            model_name="user",
            name="email",
            field=models.EmailField(
                unique=True,
                max_length=254,
                verbose_name="email address",
                blank=True,
            ),
        ),
        migrations.AlterField(
            model_name="user",
            name="groups",
            field=models.ManyToManyField(
                related_query_name="user",
                related_name="user_set",
                to="auth.Group",
                blank=True,
                help_text="The groups this user belongs to. A user will get all permissions granted to each of their groups.",
                verbose_name="groups",
            ),
        ),
        migrations.AlterField(
            model_name="user",
            name="last_login",
            field=models.DateTimeField(
                null=True, verbose_name="last login", blank=True
            ),
        ),
        migrations.AlterField(
            model_name="user",
            name="username",
            field=models.CharField(
                error_messages={
                    "unique": "A user with that username already exists."
                },
                max_length=30,
                validators=[
                    django.core.validators.RegexValidator(
                        "^[\\w.@+-]+$",
                        "Enter a valid username. This value may contain only letters, numbers and @/./+/-/_ characters.",
                        "invalid",
                    )
                ],
                help_text="Required. 30 characters or fewer. Letters, digits and @/./+/-/_ only.",
                unique=True,
                verbose_name="username",
            ),
        ),
    ]
