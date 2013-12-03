# Copyright 2013 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the user accounts API."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

import httplib
import json

from django.contrib.auth.models import User
from django.core.urlresolvers import reverse
from maasserver.testing.api import APITestCase
from maasserver.testing.factory import factory
from maastesting.matchers import ContainsAll


class TestUsers(APITestCase):

    def test_handler_path(self):
        self.assertEqual(
            '/api/1.0/users/', reverse('users_handler'))

    def test_POST_creates_user(self):
        self.become_admin()
        username = factory.make_name('user')
        email = factory.getRandomEmail()
        password = factory.getRandomString()

        response = self.client.post(
            reverse('users_handler'),
            {
                'username': username,
                'email': email,
                'password': password,
                'is_superuser': '0',
            })
        self.assertEqual(httplib.OK, response.status_code, response.content)

        self.assertEqual(username, json.loads(response.content)['username'])
        created_user = User.objects.get(username=username)
        self.assertEqual(
            (email, False),
            (created_user.email, created_user.is_superuser))

    def test_POST_creates_admin(self):
        self.become_admin()
        username = factory.make_name('user')
        email = factory.getRandomEmail()
        password = factory.getRandomString()

        response = self.client.post(
            reverse('users_handler'),
            {
                'username': username,
                'email': email,
                'password': password,
                'is_superuser': '1',
            })
        self.assertEqual(httplib.OK, response.status_code, response.content)

        self.assertEqual(username, json.loads(response.content)['username'])
        created_user = User.objects.get(username=username)
        self.assertEqual(
            (email, True),
            (created_user.email, created_user.is_superuser))

    def test_POST_requires_admin(self):
        response = self.client.post(
            reverse('users_handler'),
            {
                'username': factory.make_name('user'),
                'email': factory.getRandomEmail(),
                'password': factory.getRandomString(),
                'is_superuser': '1' if factory.getRandomBoolean() else '0',
            })
        self.assertEqual(
            httplib.FORBIDDEN, response.status_code, response.content)

    def test_GET_lists_users(self):
        users = [factory.make_user() for counter in range(2)]

        response = self.client.get(reverse('users_handler'))
        self.assertEqual(httplib.OK, response.status_code, response.content)

        listing = json.loads(response.content)
        self.assertThat(
            [user['username'] for user in listing],
            ContainsAll([user.username for user in users]))

    def test_GET_orders_by_name(self):
        # Create some users.  Give them lower-case names, because collation
        # algorithms may differ on how mixed-case names should be sorted.
        # The implementation may sort in the database or in Python code, and
        # the two may use different collations.
        users = [factory.make_name('user').lower() for counter in range(5)]
        for user in users:
            factory.make_user(username=user)

        response = self.client.get(reverse('users_handler'))
        self.assertEqual(httplib.OK, response.status_code, response.content)

        listing = json.loads(response.content)
        # The listing may also contain built-in users and/or a test user.
        # Restrict it to the users we created ourselves.
        users_as_returned = [
            user['username'] for user in listing if user['username'] in users
            ]
        self.assertEqual(sorted(users), users_as_returned)


class TestUser(APITestCase):

    def test_handler_path(self):
        self.assertEqual(
            '/api/1.0/users/username/',
            reverse('user_handler', args=['username']))

    def test_GET_finds_user(self):
        user = factory.make_user()

        response = self.client.get(
            reverse('user_handler', args=[user.username]))
        self.assertEqual(httplib.OK, response.status_code, response.content)

        returned_user = json.loads(response.content)
        self.assertEqual(user.username, returned_user['username'])
        self.assertEqual(user.email, returned_user['email'])
        self.assertFalse(returned_user['is_superuser'])

    def test_GET_shows_expected_fields(self):
        user = factory.make_user()

        response = self.client.get(
            reverse('user_handler', args=[user.username]))
        self.assertEqual(httplib.OK, response.status_code, response.content)

        returned_user = json.loads(response.content)
        self.assertItemsEqual(
            ['username', 'email', 'is_superuser'],
            returned_user.keys())

    def test_GET_identifies_superuser_as_such(self):
        user = factory.make_admin()

        response = self.client.get(
            reverse('user_handler', args=[user.username]))
        self.assertEqual(httplib.OK, response.status_code, response.content)

        self.assertTrue(json.loads(response.content)['is_superuser'])

    def test_GET_returns_404_if_user_not_found(self):
        nonuser = factory.make_name('nonuser')
        response = self.client.get(reverse('user_handler', args=[nonuser]))
        self.assertEqual(
            httplib.NOT_FOUND, response.status_code, response.status_code)
        self.assertItemsEqual([], User.objects.filter(username=nonuser))
