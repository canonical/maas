import pytest


@pytest.mark.asyncio
async def test_db_no_commits_by_default(db_connection):
    with pytest.raises(AssertionError):
        await db_connection.commit()


@pytest.mark.allow_transactions
@pytest.mark.asyncio
async def test_db_commits_with_allow_transactions(db_connection):
    await db_connection.commit()
