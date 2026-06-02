from django.contrib import admin
from django.contrib.auth.models import User
from django.db import models


class Blogpost(models.Model):
    title = models.CharField(max_length=255)
    content = models.TextField()
    author = models.ForeignKey(User, related_name="posts")
    created_on = models.DateTimeField(auto_now_add=True)

    def __unicode__(self):
        return self.title


admin.site.register(Blogpost)
