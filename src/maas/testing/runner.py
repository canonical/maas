from subprocess import check_call
from django.test.simple import DjangoTestSuiteRunner


class CustomTestRunner(DjangoTestSuiteRunner):
    """Custom test runner; ensures that the test database cluster is up."""

    def setup_databases(self, *args, **kwargs):
        """Fire up the db cluster, then punt to original implementation."""
        check_call(['bin/maasdb', 'start', './db/', 'disposable'])
        return super(CustomTestRunner, self).setup_databases(*args, **kwargs)
