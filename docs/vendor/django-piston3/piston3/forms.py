import base64
import hmac

from django import forms
from django.conf import settings


class Form(forms.Form):
    pass


class ModelForm(forms.ModelForm):
    """
    Subclass of `forms.ModelForm` which makes sure
    that the initial values are present in the form
    data, so you don't have to send all old values
    for the form to actually validate. Django does not
    do this on its own, which is really annoying.
    """

    def merge_from_initial(self):
        self.data._mutable = True

        fields = [
            field
            for field in getattr(self.Meta, "fields", ())
            if field not in self.data.keys()
        ]
        for field in fields:
            self.data[field] = self.initial.get(field, None)


class OAuthAuthenticationForm(forms.Form):
    oauth_token = forms.CharField(widget=forms.HiddenInput)
    oauth_callback = forms.CharField(widget=forms.HiddenInput, required=False)
    authorize_access = forms.BooleanField(required=True)
    csrf_signature = forms.CharField(widget=forms.HiddenInput)

    def __init__(self, *args, **kwargs):
        forms.Form.__init__(self, *args, **kwargs)

        self.fields["csrf_signature"].initial = self.initial_csrf_signature

    def clean_csrf_signature(self):
        sig = self.cleaned_data["csrf_signature"]
        token = self.cleaned_data["oauth_token"]

        sig1 = OAuthAuthenticationForm.get_csrf_signature(
            settings.SECRET_KEY, token
        )

        if sig != sig1:
            raise forms.ValidationError("CSRF signature is not valid")

        return sig

    def initial_csrf_signature(self):
        token = self.initial["oauth_token"]
        return OAuthAuthenticationForm.get_csrf_signature(
            settings.SECRET_KEY, token
        )

    @staticmethod
    def get_csrf_signature(key, token):
        # Check signature...
        import hashlib  # 2.5

        # PY3: hmac doesn't work with str
        key = key.encode("ascii")
        token = token.encode("ascii")
        hashed = hmac.new(key, token, hashlib.sha1)

        # calculate the digest base 64 (PY3: returns bytes)
        signature = base64.b64encode(hashed.digest())
        # PY3: decode to get str
        return signature.decode("ascii")
