from django.shortcuts import render

from blogserver.blog.models import Blogpost


def posts(request):
    posts = Blogpost.objects.all()

    return render(request, "posts.html", {"posts": posts})


def test_js(request):
    return render(request, "test_js.html", {})
