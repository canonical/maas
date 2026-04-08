# MAAS API v2 Reference

This is the documentation for the API that lets you control and query MAAS. The API is "RESTful", which means that you access it through normal HTTP requests.

## API versions

At any given time, MAAS may support multiple versions of its API. The version number is included in the API's URL, e.g. `/api/2.0/`

For now, 2.0 is the only supported version.

The current API version number can be retrieved by issuing a GET to `/api/version/`. Accessing an old or unknown API version URL will result in a "410 GONE" being returned, along with a descriptive error message. Both the error message and the api version are returned as plaintext.

## HTTP methods and parameter-passing

The following HTTP methods are available for accessing the API:

- GET (for information retrieval and queries),
- POST (for asking the system to do things),
- PUT (for updating objects), and
- DELETE (for deleting objects).

All methods except DELETE may take parameters, but they are not all passed in the same way. GET parameters are passed in the URL, as is normal with a GET: `/item/?foo=bar` passes parameter "foo" with value "bar".

POST and PUT are different. Your request should have MIME type `multipart/form-data`; each part represents one parameter (for POST) or attribute (for PUT). Each part is named after the parameter or attribute it contains, and its contents are the conveyed value.

All parameters are in text form. If you need to submit binary data to the API, don't send it as any MIME binary format; instead, send it as a plain text part containing base64-encoded data.

Most resources offer a choice of GET or POST operations. In those cases these methods will take one special parameter, called `op`, to indicate what it is you want to do.

For example, to list all machines, you might GET `/MAAS/api/2.0/machines/`.
