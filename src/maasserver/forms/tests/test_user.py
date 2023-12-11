# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for user-creation forms."""


from django.contrib.auth.models import User

from maasserver.forms import EditUserForm, NewUserCreationForm, ProfileForm
from maasserver.secrets import SecretManager
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase


class TestUniqueEmailForms(MAASServerTestCase):
    def assertFormFailsValidationBecauseEmailNotUnique(self, form):
        self.assertFalse(form.is_valid())
        self.assertIn("email", form._errors)
        self.assertEqual(1, len(form._errors["email"]))
        # Cope with 'Email' and 'E-mail' in error message.
        self.assertRegex(
            form._errors["email"][0],
            r"User with this E-{0,1}mail address already exists.",
        )

    def test_ProfileForm_fails_validation_if_email_taken(self):
        another_email = "%s@example.com" % factory.make_string()
        factory.make_User(email=another_email)
        email = "%s@example.com" % factory.make_string()
        user = factory.make_User(email=email)
        form = ProfileForm(instance=user, data={"email": another_email})
        self.assertFormFailsValidationBecauseEmailNotUnique(form)

    def test_ProfileForm_validates_if_email_unchanged(self):
        email = "%s@example.com" % factory.make_string()
        user = factory.make_User(email=email)
        form = ProfileForm(instance=user, data={"email": email})
        self.assertTrue(form.is_valid(), form.errors)

    def test_NewUserCreationForm_fails_validation_if_email_taken(self):
        email = "%s@example.com" % factory.make_string()
        username = factory.make_string()
        password = factory.make_string()
        factory.make_User(email=email)
        form = NewUserCreationForm(
            {
                "email": email,
                "username": username,
                "password1": password,
                "password2": password,
            }
        )
        self.assertFormFailsValidationBecauseEmailNotUnique(form)

    def test_EditUserForm_fails_validation_if_email_taken(self):
        another_email = "%s@example.com" % factory.make_string()
        factory.make_User(email=another_email)
        email = "%s@example.com" % factory.make_string()
        user = factory.make_User(email=email)
        form = EditUserForm(instance=user, data={"email": another_email})
        self.assertFormFailsValidationBecauseEmailNotUnique(form)

    def test_EditUserForm_validates_if_email_unchanged(self):
        email = "%s@example.com" % factory.make_string()
        user = factory.make_User(email=email)
        form = EditUserForm(
            instance=user,
            data={"email": email, "username": factory.make_string()},
        )
        self.assertTrue(form.is_valid(), form.errors)


class TestNewUserCreationForm(MAASServerTestCase):
    def test_saves_to_db_by_default(self):
        password = factory.make_name("password")
        params = {
            "email": "%s@example.com" % factory.make_string(),
            "username": factory.make_name("user"),
            "password1": password,
            "password2": password,
        }
        form = NewUserCreationForm(params)
        form.save()
        self.assertIsNotNone(User.objects.get(username=params["username"]))

    def test_email_is_required(self):
        password = factory.make_name("password")
        params = {
            "email": "",
            "username": factory.make_name("user"),
            "password1": password,
            "password2": password,
        }
        form = NewUserCreationForm(params)
        self.assertFalse(form.is_valid())
        self.assertEqual({"email": ["This field is required."]}, form._errors)

    def test_does_not_save_to_db_if_commit_is_False(self):
        password = factory.make_name("password")
        params = {
            "email": "%s@example.com" % factory.make_string(),
            "username": factory.make_name("user"),
            "password1": password,
            "password2": password,
        }
        form = NewUserCreationForm(params)
        form.save(commit=False)
        self.assertCountEqual(
            [], User.objects.filter(username=params["username"])
        )

    def test_fields_order(self):
        form = NewUserCreationForm()

        self.assertEqual(
            [
                "username",
                "last_name",
                "email",
                "password1",
                "password2",
                "is_superuser",
            ],
            list(form.fields),
        )

    def test_password_not_required_with_external_auth(self):
        SecretManager().set_composite_secret(
            "external-auth",
            {"url": "http://auth.example.com"},
        )
        form = NewUserCreationForm()
        params = {
            "email": factory.make_email(),
            "username": factory.make_name("user"),
        }
        form = NewUserCreationForm(params)
        user = form.save()
        self.assertFalse(user.has_usable_password())
