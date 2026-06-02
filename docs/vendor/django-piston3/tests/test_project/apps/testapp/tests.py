import base64
import json
import tempfile
from xml.etree import ElementTree

from django.conf import settings
from django.contrib.auth.models import User
from django.test import TestCase
from django.test.client import (
    MULTIPART_CONTENT,
    Client,
)
from django.urls import reverse
import yaml

from piston3 import oauth
from piston3.forms import OAuthAuthenticationForm
from piston3.models import (
    Consumer,
    Token,
)
from test_project.apps.testapp import signals
from test_project.apps.testapp.models import (
    CircularA,
    CircularB,
    CircularC,
    ConditionalFieldsModel,
    ExpressiveSampleModel,
    InheritedModel,
    Issue58Model,
    ListFieldsModel,
    SampleModel,
)


class MultiPartPutTestClient(Client):
    """A test client which supports multipart PUTs."""

    def put(
        self,
        path,
        data=None,
        content_type=MULTIPART_CONTENT,
        secure=False,
        **extra,
    ):
        """Construct a PUT request."""
        # this is a copy of the original post() method, which supports
        # multipart encoding.
        data = self._encode_json({} if data is None else data, content_type)
        put_data = self._encode_data(data, content_type)
        return self.generic(
            "PUT", path, put_data, content_type, secure=secure, **extra
        )


class MainTests(TestCase):
    client_class = MultiPartPutTestClient

    def setUp(self):
        self.user = User.objects.create_user(
            "admin", "admin@world.com", "admin"
        )
        self.user.is_staff = True
        self.user.is_superuser = True
        self.user.is_active = True
        self.user.save()
        auth = base64.encodebytes(b"admin:admin").rstrip()
        self.auth_string = "Basic {}".format(auth.decode("ascii"))

        if hasattr(self, "init_delegate"):
            self.init_delegate()

    def tearDown(self):
        self.user.delete()


class OAuthTests(MainTests):
    signature_method = oauth.OAuthSignatureMethod_HMAC_SHA1()

    def setUp(self):
        super().setUp()

        self.consumer = Consumer.objects.create_consumer("Test Consumer")
        self.consumer.status = "accepted"
        self.consumer.save()

    def tearDown(self):
        super().tearDown()
        self.consumer.delete()

    def test_handshake(self):
        """Test the OAuth handshake procedure"""
        oaconsumer = oauth.OAuthConsumer(
            self.consumer.key, self.consumer.secret
        )

        # Get a request key...
        request = oauth.OAuthRequest.from_consumer_and_token(
            oaconsumer, http_url="http://testserver/api/oauth/request_token"
        )
        request.sign_request(self.signature_method, oaconsumer, None)

        response = self.client.get(
            "/api/oauth/request_token", request.parameters
        )
        oatoken = oauth.OAuthToken.from_string(
            response.content.decode("utf-8")
        )

        token = Token.objects.get(key=oatoken.key, token_type=Token.REQUEST)
        self.assertEqual(token.secret, oatoken.secret)

        # Simulate user authentication...
        self.assertTrue(self.client.login(username="admin", password="admin"))
        request = oauth.OAuthRequest.from_token_and_callback(
            token=oatoken,
            callback="http://printer.example.com/request_token_ready",
            http_url="http://testserver/api/oauth/authorize",
        )
        request.sign_request(self.signature_method, oaconsumer, oatoken)

        # Request the login page
        # TODO: Parse the response to make sure all the fields exist
        #        response = self.client.get('/api/oauth/authorize', {
        #            'oauth_token': oatoken.key,
        #            'oauth_callback': 'http://printer.example.com/request_token_ready',
        #            })

        response = self.client.post(
            "/api/oauth/authorize",
            {
                "oauth_token": oatoken.key,
                "oauth_callback": "http://printer.example.com/request_token_ready",
                "csrf_signature": OAuthAuthenticationForm.get_csrf_signature(
                    settings.SECRET_KEY, oatoken.key
                ),
                "authorize_access": 1,
            },
        )

        # Response should be a redirect...
        self.assertEqual(302, response.status_code)
        self.assertTrue(
            response["Location"].startswith(
                "http://printer.example.com/request_token_ready?"
            )
        )
        self.assertTrue("oauth_token=" + oatoken.key in response["Location"])

        # Actually we can't test this last part, since it's 1.0a.
        # Obtain access token...


#        request = oauth.OAuthRequest.from_consumer_and_token(oaconsumer, token=oatoken,
#                http_url='http://testserver/api/oauth/access_token')
#        request.sign_request(self.signature_method, oaconsumer, oatoken)
#        response = self.client.get('/api/oauth/access_token', request.parameters)

#        oa_atoken = oauth.OAuthToken.from_string(response.content)
#        atoken = Token.objects.get(key=oa_atoken.key, token_type=Token.ACCESS)
#        self.assertEqual(atoken.secret, oa_atoken.secret)


class BasicAuthTest(MainTests):
    def test_invalid_auth_header(self):
        response = self.client.get("/api/entries/")
        self.assertEqual(response.status_code, 401)

        # no space
        bad_auth_string = "Basic{}".format(
            base64.encodebytes(b"admin:admin").rstrip()
        )
        response = self.client.get(
            "/api/entries/", HTTP_AUTHORIZATION=bad_auth_string
        )
        self.assertEqual(response.status_code, 401)

        # no colon
        bad_auth_string = "Basic {}".format(
            base64.encodebytes(b"adminadmin").rstrip()
        )
        response = self.client.get(
            "/api/entries/", HTTP_AUTHORIZATION=bad_auth_string
        )
        self.assertEqual(response.status_code, 401)

        # non base64 data
        bad_auth_string = "Basic FOOBARQ!"
        response = self.client.get(
            "/api/entries/", HTTP_AUTHORIZATION=bad_auth_string
        )
        self.assertEqual(response.status_code, 401)


class TestMultipleAuthenticators(MainTests):
    def test_both_authenticators(self):
        for username, password in (
            ("admin", "admin"),
            ("admin", "secr3t"),
            ("admin", "user"),
            ("admin", "allwork"),
            ("admin", "thisisneat"),
        ):
            auth = f"{username}:{password}"
            auth = auth.encode("ascii")  # base64 only operates on bytes
            auth = base64.encodebytes(auth).rstrip()
            auth = auth.decode("ascii")
            auth_string = f"Basic {auth}"

            response = self.client.get(
                "/api/multiauth/", HTTP_AUTHORIZATION=auth_string
            )

            self.assertEqual(
                response.status_code,
                200,
                f"Failed with combo of {username}:{password}",
            )


class MultiXMLTests(MainTests):
    def test_multixml(self):
        obj1 = SampleModel()
        obj1.save()
        obj2 = SampleModel()
        obj2.save()
        result = self.client.get(
            "/api/entries.xml", HTTP_AUTHORIZATION=self.auth_string
        )
        result_xml = ElementTree.fromstring(result.content)
        self.assertCountEqual(
            [[elem.tag for elem in res] for res in result_xml],
            [
                ["test1", "test2", "resource_uri"],
                ["test1", "test2", "resource_uri"],
            ],
        )

    def test_singlexml(self):
        obj = SampleModel()
        obj.save()
        result = self.client.get(
            f"/api/entry-{obj.pk}.xml", HTTP_AUTHORIZATION=self.auth_string
        )
        result_xml = ElementTree.fromstring(result.content)
        self.assertCountEqual(
            [elem.tag for elem in result_xml],
            ["test1", "test2", "resource_uri"],
        )


class TestModelClass(MainTests):
    def test_resource_uri(self):
        obj = SampleModel(test1="foo", test2="bar")
        obj.save()
        resp = self.client.get(
            f"/api/entries/{obj.pk}/?format=json",
            HTTP_AUTHORIZATION=self.auth_string,
        )
        self.assertEqual(
            resp.json(),
            {
                "test1": "foo",
                "test2": "bar",
                "resource_uri": f"/api/entries/{obj.pk}/",
            },
        )


class AbstractBaseClassTests(MainTests):
    def init_delegate(self):
        self.ab1 = InheritedModel()
        self.ab1.save()
        self.ab2 = InheritedModel()
        self.ab2.save()

    def test_field_presence(self):
        result = self.client.get(
            "/api/abstract.json", HTTP_AUTHORIZATION=self.auth_string
        ).content

        expected = [
            {
                "id": 1,
                "some_other": "something else",
                "some_field": "something here",
            },
            {
                "id": 2,
                "some_other": "something else",
                "some_field": "something here",
            },
        ]

        self.assertEqual(json.loads(result.decode("utf-8")), expected)

    def test_specific_id(self):
        ids = (1, 2)
        expected = {
            "some_other": "something else",
            "some_field": "something here",
        }

        for id_ in ids:
            result = self.client.get(
                "/api/abstract/%d.json" % id_,
                HTTP_AUTHORIZATION=self.auth_string,
            ).content

            expected["id"] = id_

            self.assertEqual(json.loads(result.decode("utf-8")), expected)


class IncomingExpressiveTests(MainTests):
    def init_delegate(self):
        e1 = ExpressiveSampleModel(title="foo", content="bar")
        e1.save()
        e2 = ExpressiveSampleModel(title="foo2", content="bar2")
        e2.save()

    def test_incoming_json(self):
        post = {
            "title": "test",
            "content": "test",
            "comments": [{"content": "test1"}, {"content": "test2"}],
        }
        outgoing = json.dumps(post)

        expected = [
            {"content": "bar", "comments": [], "title": "foo"},
            {"content": "bar2", "comments": [], "title": "foo2"},
        ]

        result = self.client.get(
            "/api/expressive.json", HTTP_AUTHORIZATION=self.auth_string
        ).content

        self.assertEqual(json.loads(result.decode("utf-8")), expected)

        resp = self.client.post(
            "/api/expressive.json",
            outgoing,
            content_type="application/json",
            HTTP_AUTHORIZATION=self.auth_string,
        )

        self.assertEqual(resp.status_code, 201)

        expected.append(post)

        result = self.client.get(
            "/api/expressive.json", HTTP_AUTHORIZATION=self.auth_string
        ).content

        self.assertEqual(json.loads(result.decode("utf-8")), expected)

    def test_incoming_invalid_json(self):
        resp = self.client.post(
            "/api/expressive.json",
            "foo",
            HTTP_AUTHORIZATION=self.auth_string,
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_incoming_yaml(self):
        if not yaml:
            return

        expected = b"""- comments: []
  content: bar
  title: foo
- comments: []
  content: bar2
  title: foo2
"""

        self.assertEqual(
            self.client.get(
                "/api/expressive.yaml", HTTP_AUTHORIZATION=self.auth_string
            ).content,
            expected,
        )

        outgoing = yaml.dump(
            {
                "title": "test",
                "content": "test",
                "comments": [{"content": "test1"}, {"content": "test2"}],
            }
        )

        resp = self.client.post(
            "/api/expressive.json",
            outgoing,
            content_type="application/x-yaml",
            HTTP_AUTHORIZATION=self.auth_string,
        )

        self.assertEqual(resp.status_code, 201)

        expected = b"""- comments: []
  content: bar
  title: foo
- comments: []
  content: bar2
  title: foo2
- comments:
  - content: test1
  - content: test2
  content: test
  title: test
"""
        self.assertEqual(
            self.client.get(
                "/api/expressive.yaml", HTTP_AUTHORIZATION=self.auth_string
            ).content,
            expected,
        )

    def test_incoming_invalid_yaml(self):
        resp = self.client.post(
            "/api/expressive.yaml",
            "  8**sad asj lja foo",
            HTTP_AUTHORIZATION=self.auth_string,
            content_type="application/x-yaml",
        )
        self.assertEqual(resp.status_code, 400)


class Issue36RegressionTests(MainTests):
    """
    This testcase addresses #36 in django-piston where request.FILES is passed
    empty to the handler if the request.method is PUT.
    """

    def fetch_request(self, sender, request, *args, **kwargs):
        self.request = request

    def setUp(self):
        super(self.__class__, self).setUp()
        self.data = SampleModel()
        self.data.save()
        # Register to the WSGIRequest signals to get the latest generated
        # request object.
        signals.entry_request_started.connect(self.fetch_request)

    def tearDown(self):
        super(self.__class__, self).tearDown()
        self.data.delete()
        signals.entry_request_started.disconnect(self.fetch_request)

    def test_simple(self):
        # First try it with POST to see if it works there
        fp = open(__file__, "rb")  # Need binary file for client data
        try:
            self.client.post(
                "/api/entries.xml",
                {"file": fp},
                HTTP_AUTHORIZATION=self.auth_string,
            )
            self.assertEqual(
                1,
                len(self.request.FILES),
                "request.FILES on POST is empty when it should contain 1 file",
            )
        finally:
            fp.close()

        if not hasattr(self.client, "put"):
            import warnings

            warnings.warn(
                "Issue36RegressionTest partially requires Django 1.1 or newer. Skipped."
            )
            return

        # ... and then with PUT
        fp = open(__file__)
        try:
            self.client.put(
                "/api/entry-%d.xml" % self.data.pk,
                {"file": fp},
                HTTP_AUTHORIZATION=self.auth_string,
                content_type=MULTIPART_CONTENT,
            )
            self.assertEqual(
                1,
                len(self.request.FILES),
                "request.FILES on PUT is empty when it should contain 1 file",
            )
        finally:
            fp.close()


class ValidationTest(MainTests):
    def test_basic_validation_fails(self):
        resp = self.client.get("/api/echo")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(
            resp.content,
            b'Bad Request <ul class="errorlist">'
            b'<li>msg<ul class="errorlist"><li>This field is required.</li>'
            b"</ul></li></ul>",
        )

    def test_basic_validation_succeeds(self):
        data = {"msg": "donuts!"}
        resp = self.client.get("/api/echo", data)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(data, json.loads(resp.content.decode("utf-8")))


class PlainOldObject(MainTests):
    def test_plain_object_serialization(self):
        resp = self.client.get("/api/popo")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            {"type": "plain", "field": "a field"},
            json.loads(resp.content.decode("utf-8")),
        )


class ListFieldsTest(MainTests):
    def init_delegate(self):
        ListFieldsModel(kind="fruit", variety="apple", color="green").save()
        ListFieldsModel(
            kind="vegetable", variety="carrot", color="orange"
        ).save()
        ListFieldsModel(kind="animal", variety="dog", color="brown").save()

    def test_single_item(self):
        expect = {
            "color": "green",
            "kind": "fruit",
            "id": 1,
            "variety": "apple",
        }
        resp = self.client.get("/api/list_fields/1")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(json.loads(resp.content.decode("utf-8")), expect)

    def test_multiple_items(self):
        expect = [
            {"id": 1, "variety": "apple"},
            {"id": 2, "variety": "carrot"},
            {"id": 3, "variety": "dog"},
        ]
        resp = self.client.get("/api/list_fields")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(json.loads(resp.content.decode("utf-8")), expect)


class ErrorHandlingTests(MainTests):
    """Test proper handling of errors by Resource"""

    def test_response_not_allowed(self):
        resp = self.client.post("/api/echo")
        self.assertEqual(resp.status_code, 405)
        self.assertEqual(resp["Allow"], "GET, HEAD")

    def test_not_found_because_of_unexpected_http_method(self):
        # not using self.client.head because it is not present in Django 1.0
        resp = self.client.get("/api/echo", REQUEST_METHOD="HEAD")
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(resp.content, b"")


class Issue58ModelTests(MainTests):
    """
    This testcase addresses #58 in django-piston where if a model
    has one of the ['read','update','delete','create'] defined
    it make piston crash with a `TypeError`
    """

    def init_delegate(self):
        m1 = Issue58Model(read=True, model="t")
        m1.save()
        m2 = Issue58Model(read=False, model="f")
        m2.save()

    def test_incoming_json(self):
        outgoing = json.dumps({"read": True, "model": "T"})

        expected = [
            {"read": True, "model": "t"},
            {"read": False, "model": "f"},
        ]

        # test GET
        result = self.client.get(
            "/api/issue58.json", HTTP_AUTHORIZATION=self.auth_string
        ).content
        self.assertEqual(json.loads(result.decode("utf-8")), expected)

        # test POST
        resp = self.client.post(
            "/api/issue58.json",
            outgoing,
            content_type="application/json",
            HTTP_AUTHORIZATION=self.auth_string,
        )
        self.assertEqual(resp.status_code, 201)


class Issue188ValidateWithFiles(MainTests):
    def test_whoops_no_file_upload(self):
        resp = self.client.post(
            reverse("file-upload-test"), data={"chaff": "pewpewpew"}
        )
        self.assertEqual(resp.status_code, 400)

    def test_upload_with_file(self):
        tmp_fs = tempfile.NamedTemporaryFile(suffix=".txt")
        content = b"le_content"
        tmp_fs.write(content)
        tmp_fs.seek(0)
        resp = self.client.post(
            reverse("file-upload-test"),
            data={"chaff": "pewpewpew", "le_file": tmp_fs},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            json.loads(resp.content.decode("utf-8")),
            {"chaff": "pewpewpew", "file_size": len(content)},
        )


class EmitterFormat(MainTests):
    def test_format_in_url(self):
        resp = self.client.get(
            "/api/entries.json", HTTP_AUTHORIZATION=self.auth_string
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            resp["Content-type"], "application/json; charset=utf-8"
        )
        resp = self.client.get(
            "/api/entries.xml", HTTP_AUTHORIZATION=self.auth_string
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-type"], "text/xml; charset=utf-8")
        resp = self.client.get(
            "/api/entries.yaml", HTTP_AUTHORIZATION=self.auth_string
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            resp["Content-type"], "application/x-yaml; charset=utf-8"
        )

    def test_format_in_get_data(self):
        resp = self.client.get(
            "/api/entries/?format=json", HTTP_AUTHORIZATION=self.auth_string
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            resp["Content-type"], "application/json; charset=utf-8"
        )
        resp = self.client.get(
            "/api/entries/?format=xml", HTTP_AUTHORIZATION=self.auth_string
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-type"], "text/xml; charset=utf-8")
        resp = self.client.get(
            "/api/entries/?format=yaml", HTTP_AUTHORIZATION=self.auth_string
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            resp["Content-type"], "application/x-yaml; charset=utf-8"
        )


class ConditionalFieldsTest(MainTests):
    def setUp(self):
        super().setUp()
        self.test_model_obj = SampleModel.objects.create(test1="a", test2="b")
        self.cond_fields_obj = ConditionalFieldsModel.objects.create(
            field_one="c", field_two="d", fk_field=self.test_model_obj
        )

    def test_conditional_list_fields(self):
        response = self.client.get(reverse("conditional-list"))
        response_obj = json.loads(response.content.decode("utf-8"))
        self.assertEqual(len(response_obj), 1)
        response_struct = response_obj[0]
        self.assertEqual(list(response_struct.keys()), ["field_two"])
        self.assertEqual(response_struct["field_two"], "d")
        response = self.client.get(
            reverse("conditional-list"), HTTP_AUTHORIZATION=self.auth_string
        )
        response_obj = json.loads(response.content.decode("utf-8"))
        self.assertEqual(len(response_obj), 1)
        response_struct = response_obj[0]
        self.assertEqual(len(response_struct.keys()), 2)
        self.assertTrue("field_one" in response_struct.keys())
        self.assertTrue("field_two" in response_struct.keys())
        self.assertEqual(response_struct["field_one"], "c")
        self.assertEqual(response_struct["field_two"], "d")

    def test_conditional_detail_fields(self):
        response = self.client.get(
            reverse("conditional-detail", args=[self.cond_fields_obj.pk])
        )
        response_obj = json.loads(response.content.decode("utf-8"))
        self.assertEqual(list(response_obj.keys()), ["field_one"])
        self.assertEqual(response_obj["field_one"], "c")
        response = self.client.get(
            reverse("conditional-detail", args=[self.cond_fields_obj.pk]),
            HTTP_AUTHORIZATION=self.auth_string,
        )
        response_obj = json.loads(response.content.decode("utf-8"))
        self.assertEqual(len(response_obj.keys()), 3)
        self.assertTrue("field_one" in response_obj.keys())
        self.assertTrue("field_two" in response_obj.keys())
        self.assertTrue("fk_field" in response_obj.keys())
        self.assertEqual(response_obj["field_one"], "c")
        self.assertEqual(response_obj["field_two"], "d")
        self.assertEqual(type(response_obj["fk_field"]), dict)

    def test_format_in_accept_headers(self):
        resp = self.client.get(
            "/api/entries/",
            HTTP_AUTHORIZATION=self.auth_string,
            HTTP_ACCEPT="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            resp["Content-type"], "application/json; charset=utf-8"
        )
        resp = self.client.get(
            "/api/entries/",
            HTTP_AUTHORIZATION=self.auth_string,
            HTTP_ACCEPT="text/xml",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-type"], "text/xml; charset=utf-8")
        resp = self.client.get(
            "/api/entries/",
            HTTP_AUTHORIZATION=self.auth_string,
            HTTP_ACCEPT="application/x-yaml",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            resp["Content-type"], "application/x-yaml; charset=utf-8"
        )

    def test_strict_accept_headers(self):
        from . import urls

        self.assertFalse(urls.entries.strict_accept)
        self.assertEqual(urls.entries.default_emitter, "json")
        resp = self.client.get(
            "/api/entries/",
            HTTP_AUTHORIZATION=self.auth_string,
            HTTP_ACCEPT="text/html",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            resp["Content-type"], "application/json; charset=utf-8"
        )
        urls.entries.strict_accept = True
        resp = self.client.get(
            "/api/entries/",
            HTTP_AUTHORIZATION=self.auth_string,
            HTTP_ACCEPT="text/html",
        )
        self.assertEqual(resp.status_code, 406)


class CircularReferenceTest(MainTests):
    def init_delegate(self):
        self.a = CircularA.objects.create(name="foo")
        self.b = CircularB.objects.create(name="bar")
        self.c = CircularC.objects.create(name="baz")
        self.a.link = self.b
        self.a.save()
        self.b.link = self.c
        self.b.save()
        self.c.link = self.a
        self.c.save()

    def test_circular_model_references(self):
        self.assertRaises(
            RuntimeError,
            self.client.get,
            "/api/circular_a/",
            HTTP_AUTHORIZATION=self.auth_string,
        )
