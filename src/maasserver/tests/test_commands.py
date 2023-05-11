# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test custom commands, as found in src/maasserver/management/commands."""


import io
from io import StringIO
import random

from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError
from requests.exceptions import RequestException
from testtools.matchers import AfterPreprocessing, HasLength

from apiclient.creds import convert_tuple_to_string
from maasserver.enum import KEYS_PROTOCOL_TYPE
from maasserver.management.commands import changepasswords, createadmin
import maasserver.models.keysource as keysource_module
from maasserver.models.sshkey import SSHKey
from maasserver.models.user import get_creds_tuple
from maasserver.secrets import SecretManager
from maasserver.testing import get_data
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.orm import get_one, reload_object


def assertCommandErrors(runner, command, *args, **kwargs):
    """Assert that the given django command fails.

    This method returns the error text.
    """
    # Django >= 1.5 puts error text in exception.
    exception = runner.assertRaises(
        CommandError, call_command, command, *args, **kwargs
    )
    return str(exception)


# Is the given buffer empty or does it contain only whitespace?
IsEmpty = AfterPreprocessing(lambda buf: buf.getvalue().strip(), HasLength(0))


class TestCommands(MAASServerTestCase):
    """Happy-path integration testing for custom commands.

    Detailed testing does not belong here.  If there's any complexity at all
    in a command's code, it should be extracted and unit-tested separately.
    """

    def test_generate_api_doc(self):
        stdout = StringIO()
        call_command("generate_api_doc", stdout=stdout)
        result = stdout.getvalue()
        # Just check that the documentation looks all right.
        self.assertIn("POST /MAAS/api/2.0/account/", result)
        self.assertIn("MAAS API", result)
        self.assertTrue(
            result[:20].startswith(".. _maas-api:"),
        )
        # It also contains a ReST title (not indented).
        self.assertIn("===", result[:20])

    def test_createadmin_prompts_for_password_if_not_given(self):
        stderr = StringIO()
        stdout = StringIO()
        username = factory.make_name("user")
        password = factory.make_string()
        ssh_import = "{}:{}".format(
            random.choice([KEYS_PROTOCOL_TYPE.LP, KEYS_PROTOCOL_TYPE.GH]),
            factory.make_name("user-id"),
        )
        email = factory.make_email_address()
        self.patch(createadmin, "prompt_for_password").return_value = password
        self.patch(keysource_module.KeySource, "import_keys")

        call_command(
            "createadmin",
            username=username,
            email=email,
            ssh_import=ssh_import,
            stdout=stdout,
            stderr=stderr,
        )
        user = User.objects.get(username=username)

        self.assertThat(stderr, IsEmpty)
        self.assertThat(stdout, IsEmpty)
        self.assertTrue(user.check_password(password))

    def test_createadmin_not_prompts_for_password_if_ext_auth(self):
        SecretManager().set_composite_secret(
            "external-auth", {"url": "https://example.com"}
        )
        stderr = StringIO()
        stdout = StringIO()
        username = factory.make_name("user")
        ssh_import = "{}:{}".format(
            random.choice([KEYS_PROTOCOL_TYPE.LP, KEYS_PROTOCOL_TYPE.GH]),
            factory.make_name("user-id"),
        )
        email = factory.make_email_address()
        prompt_for_password = self.patch(createadmin, "prompt_for_password")
        prompt_for_password.return_value = factory.make_string()
        self.patch(keysource_module.KeySource, "import_keys")

        call_command(
            "createadmin",
            username=username,
            email=email,
            ssh_import=ssh_import,
            stdout=stdout,
            stderr=stderr,
        )

        user = User.objects.get(username=username)
        self.assertIsNotNone(user)
        self.assertFalse(prompt_for_password.called)
        self.assertEqual("", stderr.getvalue().strip())

    def test_createadmin_prompts_for_username_if_not_given(self):
        stderr = StringIO()
        stdout = StringIO()
        username = factory.make_name("user")
        password = factory.make_string()
        email = factory.make_email_address()
        ssh_import = "{}:{}".format(
            random.choice([KEYS_PROTOCOL_TYPE.LP, KEYS_PROTOCOL_TYPE.GH]),
            factory.make_name("user-id"),
        )
        self.patch(createadmin, "prompt_for_username").return_value = username
        self.patch(keysource_module.KeySource, "import_keys")

        call_command(
            "createadmin",
            password=password,
            email=email,
            ssh_import=ssh_import,
            stdout=stdout,
            stderr=stderr,
        )
        user = User.objects.get(username=username)

        self.assertThat(stderr, IsEmpty)
        self.assertThat(stdout, IsEmpty)
        self.assertTrue(user.check_password(password))

    def test_createadmin_prompts_for_email_if_not_given(self):
        stderr = StringIO()
        stdout = StringIO()
        username = factory.make_name("user")
        password = factory.make_string()
        email = factory.make_email_address()
        ssh_import = "{}:{}".format(
            random.choice([KEYS_PROTOCOL_TYPE.LP, KEYS_PROTOCOL_TYPE.GH]),
            factory.make_name("user-id"),
        )
        self.patch(createadmin, "prompt_for_email").return_value = email
        self.patch(keysource_module.KeySource, "import_keys")

        call_command(
            "createadmin",
            username=username,
            password=password,
            ssh_import=ssh_import,
            stdout=stdout,
            stderr=stderr,
        )
        user = User.objects.get(username=username)

        self.assertThat(stderr, IsEmpty)
        self.assertThat(stdout, IsEmpty)
        self.assertTrue(user.check_password(password))

    def test_createadmin_not_prompt_for_ssh_import_if_other_params_given(self):
        stderr = StringIO()
        stdout = StringIO()
        username = factory.make_name("user")
        password = factory.make_string()
        email = factory.make_email_address()

        call_command(
            "createadmin",
            username=username,
            password=password,
            email=email,
            stdout=stdout,
            stderr=stderr,
        )

        self.assertThat(stderr, IsEmpty)
        self.assertThat(stdout, IsEmpty)

    def test_createadmin_prompts_for_ssh_import_if_not_given(self):
        stderr = StringIO()
        stdout = StringIO()
        username = factory.make_name("user")
        password = factory.make_string()
        email = factory.make_email_address()
        ssh_import = "{}:{}".format(
            random.choice([KEYS_PROTOCOL_TYPE.LP, KEYS_PROTOCOL_TYPE.GH]),
            factory.make_name("user-id"),
        )
        self.patch(
            createadmin, "prompt_for_ssh_import"
        ).return_value = ssh_import
        self.patch(keysource_module.KeySource, "import_keys")

        call_command(
            "createadmin",
            username=username,
            password=password,
            email=email,
            stdout=stdout,
            stderr=stderr,
        )
        user = User.objects.get(username=username)

        self.assertThat(stderr, IsEmpty)
        self.assertThat(stdout, IsEmpty)
        self.assertTrue(user.check_password(password))

    def test_createadmin_creates_admin_and_ssh_key(self):
        stderr = StringIO()
        stdout = StringIO()
        username = factory.make_string()
        password = factory.make_string()
        email = "%s@example.com" % factory.make_string()
        protocol = random.choice(
            [KEYS_PROTOCOL_TYPE.LP, KEYS_PROTOCOL_TYPE.GH]
        )
        user_id = factory.make_name("user-id")
        ssh_import = f"{protocol}:{user_id}"
        key_string = get_data("data/test_rsa0.pub")
        mock_get_protocol_keys = self.patch(
            keysource_module, "get_protocol_keys"
        )
        mock_get_protocol_keys.return_value = [key_string]
        call_command(
            "createadmin",
            username=username,
            password=password,
            email=email,
            ssh_import=ssh_import,
            stderr=stderr,
            stdout=stdout,
        )
        user = get_one(User.objects.filter(username=username))
        sshkey = get_one(SSHKey.objects.filter(user=user))

        self.assertThat(stderr, IsEmpty)
        self.assertThat(stdout, IsEmpty)
        self.assertTrue(user.check_password(password))
        self.assertTrue(user.is_superuser)
        self.assertEqual(email, user.email)
        self.assertEqual(key_string, sshkey.key)

    def test_createadmin_raises_ssh_key_error(self):
        stderr = StringIO()
        stdout = StringIO()
        username = factory.make_string()
        password = factory.make_string()
        email = "%s@example.com" % factory.make_string()
        ssh_import = "{}:{}".format(
            random.choice([KEYS_PROTOCOL_TYPE.LP, KEYS_PROTOCOL_TYPE.GH]),
            factory.make_name("user-id"),
        )
        self.patch(
            keysource_module.KeySource.objects, "save_keys_for_user"
        ).side_effect = RequestException("error")
        self.assertRaises(
            createadmin.SSHKeysError,
            call_command,
            "createadmin",
            username=username,
            password=password,
            email=email,
            ssh_import=ssh_import,
            stderr=stderr,
            stdout=stdout,
        )
        self.assertEqual(len(User.objects.filter(username=username)), 0)

    def test_createadmin_user_already_exists(self):
        stderr = StringIO()
        stdout = StringIO()
        username = factory.make_string()
        password = factory.make_string()
        email = "%s@example.com" % factory.make_string()
        call_command(
            "createadmin",
            username=username,
            password=password,
            email=email,
            stderr=stderr,
            stdout=stdout,
        )
        self.assertEqual(len(User.objects.filter(username=username)), 1)

        self.assertRaises(
            createadmin.AlreadyExistingUser,
            call_command,
            "createadmin",
            username=username,
            password=password,
            email=email,
            stderr=stderr,
            stdout=stdout,
        )

    def test_prompt_for_password_returns_selected_password(self):
        password = factory.make_string()
        self.patch(createadmin, "getpass").return_value = password

        self.assertEqual(password, createadmin.prompt_for_password())

    def test_prompt_for_password_checks_for_consistent_password(self):
        self.patch(createadmin, "getpass", lambda x: factory.make_string())

        self.assertRaises(
            createadmin.InconsistentPassword, createadmin.prompt_for_password
        )

    def test_prompt_for_username_returns_selected_username(self):
        username = factory.make_name("user")
        self.patch(createadmin, "read_input").return_value = username

        self.assertEqual(username, createadmin.prompt_for_username())

    def test_prompt_for_username_checks_for_empty_username(self):
        self.patch(createadmin, "read_input", lambda x: "")

        self.assertRaises(
            createadmin.EmptyUsername, createadmin.prompt_for_username
        )

    def test_prompt_for_email_returns_selected_email(self):
        email = factory.make_email_address()
        self.patch(createadmin, "read_input").return_value = email

        self.assertEqual(email, createadmin.prompt_for_email())

    def test_prompt_for_email_checks_for_empty_email(self):
        self.patch(createadmin, "read_input", lambda x: "")

        self.assertRaises(createadmin.EmptyEmail, createadmin.prompt_for_email)

    def test_prompt_for_ssh_import_returns_selected_creds(self):
        ssh_import = "{}:{}".format(
            random.choice([KEYS_PROTOCOL_TYPE.LP, KEYS_PROTOCOL_TYPE.GH]),
            factory.make_name("user-id"),
        )
        self.patch(createadmin, "read_input").return_value = ssh_import

        self.assertEqual(ssh_import, createadmin.prompt_for_ssh_import())

    def test_prompt_for_ssh_import_returns_None_for_no_user_id(self):
        self.patch(createadmin, "read_input").return_value = ""
        self.assertEqual("", createadmin.prompt_for_ssh_import())

    def test_validate_ssh_import_validates_protocol_and_user_id(self):
        protocol = random.choice(
            [KEYS_PROTOCOL_TYPE.LP, KEYS_PROTOCOL_TYPE.GH]
        )
        user_id = factory.make_name("user-id")
        ssh_import = f"{protocol}:{user_id}"
        self.assertEqual(
            (protocol, user_id), createadmin.validate_ssh_import(ssh_import)
        )

    def test_validate_ssh_import_validates_user_id_with_no_protocol(self):
        user_id = factory.make_name("user-id")
        self.assertEqual(
            (KEYS_PROTOCOL_TYPE.LP, user_id),
            createadmin.validate_ssh_import(user_id),
        )

    def test_validate_ssh_import_errors_on_incorrect_protocol(self):
        self.assertRaises(
            createadmin.SSHKeysError,
            createadmin.validate_ssh_import,
            "rubbish:good",
        )

    def test_validate_ssh_import_errors_on_incorrect_user_id(self):
        self.assertRaises(
            createadmin.SSHKeysError,
            createadmin.validate_ssh_import,
            "lp:rubbish:here",
        )


class TestChangePasswords(MAASServerTestCase):
    def test_bad_input(self):
        stdin = io.StringIO("nobody")
        self.patch(changepasswords, "fileinput").return_value = stdin
        error_text = assertCommandErrors(self, "changepasswords")
        self.assertIn(
            "Invalid input provided. "
            "Format is 'username:password', one per line.",
            error_text,
        )

    def test_nonexistent_user(self):
        stdin = io.StringIO("nobody:nopass")
        self.patch(changepasswords, "fileinput").return_value = stdin
        error_text = assertCommandErrors(self, "changepasswords")
        self.assertIn("User 'nobody' does not exist.", error_text)

    def test_changes_one_password(self):
        username = factory.make_username()
        password = factory.make_string(size=16, spaces=True, prefix="password")
        user = factory.make_User(username=username, password=password)
        self.assertTrue(user.check_password(password))
        newpass = factory.make_string(size=16, spaces=True, prefix="newpass")
        stdin = io.StringIO(f"{username}:{newpass}")
        self.patch(changepasswords, "fileinput").return_value = stdin
        call_command("changepasswords")
        self.assertTrue(reload_object(user).check_password(newpass))

    def test_changes_ten_passwords(self):
        users_passwords = []
        stringio = io.StringIO()
        for _ in range(10):
            username = factory.make_username()
            user = factory.make_User(username=username)
            newpass = factory.make_string(spaces=True, prefix="newpass")
            users_passwords.append((user, newpass))
            stringio.write(f"{username}:{newpass}\n")
        stringio.seek(0)
        self.patch(changepasswords, "fileinput").return_value = stringio
        call_command("changepasswords")
        for user, newpass in users_passwords:
            self.assertTrue(reload_object(user).check_password(newpass))


class TestApikeyCommand(MAASServerTestCase):
    def test_apikey_requires_username(self):
        error_text = assertCommandErrors(self, "apikey")
        self.assertIn(
            "You must provide a username with --username.", error_text
        )

    def test_apikey_gets_keys(self):
        stderr = StringIO()
        stdout = StringIO()
        user = factory.make_User()
        call_command(
            "apikey", username=user.username, stderr=stderr, stdout=stdout
        )
        self.assertThat(stderr, IsEmpty)

        expected_token = get_one(user.userprofile.get_authorisation_tokens())
        expected_string = (
            convert_tuple_to_string(get_creds_tuple(expected_token)) + "\n"
        )
        self.assertEqual(expected_string, stdout.getvalue())

    def test_apikey_generates_key(self):
        stderr = StringIO()
        stdout = StringIO()
        user = factory.make_User()
        num_keys = len(user.userprofile.get_authorisation_tokens())
        call_command(
            "apikey",
            username=user.username,
            generate=True,
            stderr=stderr,
            stdout=stdout,
        )
        self.assertThat(stderr, IsEmpty)
        keys_after = user.userprofile.get_authorisation_tokens()
        expected_num_keys = num_keys + 1
        self.assertEqual(expected_num_keys, len(keys_after))
        expected_token = user.userprofile.get_authorisation_tokens()[1]
        expected_string = (
            convert_tuple_to_string(get_creds_tuple(expected_token)) + "\n"
        )
        self.assertEqual(expected_string, stdout.getvalue())

    def test_apikey_deletes_key(self):
        stderr = StringIO()
        stdout = StringIO()
        user = factory.make_User()
        existing_token = get_one(user.userprofile.get_authorisation_tokens())
        token_string = convert_tuple_to_string(get_creds_tuple(existing_token))
        call_command(
            "apikey",
            username=user.username,
            delete=token_string,
            stderr=stderr,
            stdout=stdout,
        )
        self.assertThat(stderr, IsEmpty)

        keys_after = user.userprofile.get_authorisation_tokens()
        self.assertEqual(0, len(keys_after))

    def test_apikey_rejects_mutually_exclusive_options(self):
        user = factory.make_User()
        error_text = assertCommandErrors(
            self, "apikey", username=user.username, generate=True, delete="foo"
        )
        self.assertIn("Specify one of --generate or --delete", error_text)

    def test_apikey_rejects_deletion_of_bad_key(self):
        user = factory.make_User()
        error_text = assertCommandErrors(
            self, "apikey", username=user.username, delete="foo"
        )
        self.assertIn("Malformed credentials string", error_text)

    def test_api_key_rejects_deletion_of_nonexistent_key(self):
        stderr = StringIO()
        user = factory.make_User()
        existing_token = get_one(user.userprofile.get_authorisation_tokens())
        token_string = convert_tuple_to_string(get_creds_tuple(existing_token))
        call_command(
            "apikey",
            username=user.username,
            delete=token_string,
            stderr=stderr,
        )
        self.assertThat(stderr, IsEmpty)

        # Delete it again. Check that there's a sensible rejection.
        error_text = assertCommandErrors(
            self, "apikey", username=user.username, delete=token_string
        )
        self.assertIn("No matching api key found", error_text)

    def test_success_modify_apikey_name(self):
        stderr = StringIO()
        stdout = StringIO()
        fake_api_key_name = "Test Key Name"
        user = factory.make_User()
        existing_token = get_one(user.userprofile.get_authorisation_tokens())
        token_string = convert_tuple_to_string(get_creds_tuple(existing_token))
        call_command(
            "apikey",
            username=user.username,
            update=token_string,
            api_key_name=fake_api_key_name,
            stderr=stderr,
            stdout=stdout,
        )
        self.assertThat(stderr, IsEmpty)

    def test_api_key_rejects_update_of_nonexistent_key(self):
        stderr = StringIO()
        user = factory.make_User()
        fake_api_key_name = "Test Key Name"
        existing_token = get_one(user.userprofile.get_authorisation_tokens())
        token_string = convert_tuple_to_string(get_creds_tuple(existing_token))
        call_command(
            "apikey",
            username=user.username,
            delete=token_string,
            stderr=stderr,
        )
        self.assertThat(stderr, IsEmpty)

        # Try to update the deleted token.
        error_text = assertCommandErrors(
            self,
            "apikey",
            username=user.username,
            update=token_string,
            api_key_name=fake_api_key_name,
        )
        self.assertIn("No matching api key found", error_text)

    def test_api_key_rejects_update_without_key_name(self):
        user = factory.make_User()
        existing_token = get_one(user.userprofile.get_authorisation_tokens())
        token_string = convert_tuple_to_string(get_creds_tuple(existing_token))
        error_text = assertCommandErrors(
            self, "apikey", username=user.username, update=token_string
        )
        self.assertIn("Should specify new name", error_text)

    def test_api_key_update_and_generate_mutually_exclusive_options(self):
        user = factory.make_User()
        fake_api_key_name = "Test Key Name"
        existing_token = get_one(user.userprofile.get_authorisation_tokens())
        token_string = convert_tuple_to_string(get_creds_tuple(existing_token))
        error_text = assertCommandErrors(
            self,
            "apikey",
            username=user.username,
            generate=True,
            api_key_name=fake_api_key_name,
            update=token_string,
        )
        self.assertIn("Specify one of --generate or --update.", error_text)
