import pytest
from temporalio.worker import Worker as TemporalWorker

from maasserver.workflow.testing.dummy import DummyWorkflow
from maasserver.workflow.worker import Worker
from provisioningserver.utils.env import MAAS_SHARED_SECRET


class TestWorker:
    @pytest.mark.asyncio
    async def test_run(self, mocker, mock_temporal_client):
        mocker.patch("temporalio.worker.Worker.__init__", return_value=None)
        mock_worker_run = mocker.patch(
            "temporalio.worker.Worker.run", return_value=None
        )

        MAAS_SHARED_SECRET.set("x" * 32)

        wrkr = Worker(client=mock_temporal_client, workflows=[DummyWorkflow])
        await wrkr.run()

        assert isinstance(wrkr._worker, TemporalWorker)
        mock_worker_run.assert_called_once()
