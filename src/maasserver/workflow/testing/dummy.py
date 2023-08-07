from temporalio import workflow


@workflow.defn(name="DummyWorkflow", sandboxed=False)
class DummyWorkflow:
    """A no-op workflow for test purposes"""

    @workflow.run
    async def run(self) -> None:
        return
