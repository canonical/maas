This is a bare-skeleton Django application which demonstrates how you can
add an API to your own applications.

It's a simple blog application, with a "Blogpost" model, with an API on top
of it. It has a fixture which contains a sample user (used as author and 
for auth) and a couple of posts.

You can get started like so:

$ python manage.py syncdb (answer "no" when it asks for superuser creation)
$ python manage.py runserver

Now, the test user has authentication info:

Username: testuser
Password: foobar

The API is accessible via '/api/posts'. You can try it with curl:

$ curl -u testuser:foobar "http://127.0.0.1:8000/api/posts/?format=yaml"
- author: {absolute_uri: /users/testuser/, username: testuser}
  content: This is just a sample post.
  content_length: 27
  created_on: 2009-04-27 04:55:23
  title: Sample blogpost 1
- author: {absolute_uri: /users/testuser/, username: testuser}
  content: This is yet another sample post.
  content_length: 32
  created_on: 2009-04-27 04:55:33
  title: Another sample post

That's an authorized request, and the user gets back privileged information.

Anonymously:

$ curl "http://127.0.0.1:8000/api/posts/?format=yaml" 
- {content: This is just a sample post., created_on: !!timestamp '2009-04-27 04:55:23',
  title: Sample blogpost 1}
- {content: This is yet another sample post., created_on: !!timestamp '2009-04-27
    04:55:33', title: Another sample post}

Creating blog posts is also easy:

$ curl -u testuser:foobar "http://127.0.0.1:8000/api/posts/?format=yaml" -F "title=Testing again" -F "content=Foobar"
author: {absolute_uri: /users/testuser/, username: testuser}
content: Foobar
content_length: 6
created_on: 2009-04-27 05:53:38.138215
title: Testing again

(The data returned is the blog post it created.)

Anonymously that's not allowed:

$ curl -v "http://127.0.0.1:8000/api/posts/?format=yaml" -F "title=Testing again" -F "content=Foobar"
* About to connect() to 127.0.0.1 port 8000 (#0)
*   Trying 127.0.0.1... connected
* Connected to 127.0.0.1 (127.0.0.1) port 8000 (#0)
> POST /api/posts/?format=yaml HTTP/1.1
[snip]
> 
< HTTP/1.0 405 METHOD NOT ALLOWED

This is because by default, AnonymousBaseHandler has 'allow_methods' only set to 'GET'.

You can check out how this is done in the 'api' directory.

Also, there's plenty of documentation on http://bitbucket.org/jespern/django-piston/

Have fun!