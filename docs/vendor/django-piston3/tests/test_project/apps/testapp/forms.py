from django import forms


class EchoForm(forms.Form):
    msg = forms.CharField(max_length=128)


class FormWithFileField(forms.Form):
    chaff = forms.CharField(max_length=50)
    le_file = forms.FileField()
