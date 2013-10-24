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

from django.contrib.auth.models import User
from maasserver.testing.api import APITestCase
from maasserver.testing.factory import factory


class TestUsers(APITestCase):
    def test_POST_creates_user(self):
        self.become_admin()
        username = factory.make_name('user')
        email = factory.getRandomEmail()
        password = factory.getRandomString()

        response = self.client.post(
            self.get_uri('users/'),
            {
                'username': username,
                'email': email,
                'password': password,
                'is_admin': '0',
            })
        self.assertEqual(httplib.OK, response.status_code, response.content)

        created_user = User.objects.get(username=username)
        self.assertEqual(email, created_user.email)
        self.assertEqual(False, created_user.is_superuser)

    def test_POST_creates_admin(self):
        self.become_admin()
        username = factory.make_name('user')
        email = factory.getRandomEmail()
        password = factory.getRandomString()

        response = self.client.post(
            self.get_uri('users/'),
            {
                'username': username,
                'email': email,
                'password': password,
                'is_admin': '1',
            })
        self.assertEqual(httplib.OK, response.status_code, response.content)

        created_user = User.objects.get(username=username)
        self.assertEqual(email, created_user.email)
        self.assertEqual(True, created_user.is_superuser)

    def test_POST_requires_admin(self):
        response = self.client.post(
            self.get_uri('users/'),
            {
                'username': factory.make_name('user'),
                'email': factory.getRandomEmail(),
                'password': factory.getRandomString(),
                'is_admin': '1' if factory.getRandomBoolean() else '0',
            })
        self.assertEqual(
            httplib.FORBIDDEN, response.status_code, response.content)
