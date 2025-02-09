from maasserver.secrets import SecretNotFound


class FakeVaultClient:
    def __init__(self):
        self.store = {}

    def set(self, path, value):
        self.store[path] = value

    def get(self, path):
        try:
            return self.store[path]
        except KeyError:
            raise SecretNotFound(path)  # noqa: B904

    def delete(self, path):
        self.store.pop(path, None)
