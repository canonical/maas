# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


from sqlalchemy import Table
from sqlalchemy.sql.operators import eq

from maasservicelayer.db.filters import Clause, ClauseFactory
from maasservicelayer.db.repositories.base import BaseRepository
from maasservicelayer.db.tables import ConsumerTable
from maasservicelayer.models.consumers import Consumer


class ConsumerClauseFactory(ClauseFactory):
    @classmethod
    def with_user_id(cls, user_id: int) -> Clause:
        return Clause(condition=eq(ConsumerTable.c.user_id, user_id))

    @classmethod
    def with_secret(cls, secret: str) -> Clause:
        return Clause(condition=eq(ConsumerTable.c.secret, secret))

    @classmethod
    def with_key(cls, key: str) -> Clause:
        return Clause(condition=eq(ConsumerTable.c.key, key))


class ConsumersRepository(BaseRepository[Consumer]):
    """
    Piston3 Consumer repository. See
    https://github.com/userzimmermann/django-piston3/blob/fe1ea644bcb07332670aeceddbf0ded29bdf785a/piston/models.py#L55 for
    reference.

    Remove this service once all the django and its OAuth method is removed from the codebase in favor of the new JWT approach.
    """

    def get_repository_table(self) -> Table:
        return ConsumerTable

    def get_model_factory(self) -> type[Consumer]:
        return Consumer
