from django.contrib import admin

from .models import (
    Consumer,
    Nonce,
    Token,
)

admin.site.register(Nonce)
admin.site.register(Token)
admin.site.register(Consumer)
