# Copyright 2022 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).
import os
import random
import time

import pytest

maasseeds_stash = pytest.StashKey[str]()
pythonseeds_stash = pytest.StashKey[str]()


@pytest.hookimpl
def pytest_runtest_makereport(item, call):
    # If no tests were run for some reason, like skips or setup erros,
    # pythonseeds didn't get initialized.
    if call.excinfo is None or pythonseeds_stash not in item.config.stash:
        return
    python_hash_seed = item.config.stash[pythonseeds_stash]
    maas_rand_seed = item.config.stash[maasseeds_stash]
    item.add_report_section(
        "setup",
        "seeds",
        f"MAAS_RAND_SEED={maas_rand_seed} PYTHONHASHSEED={python_hash_seed}",
    )


@pytest.fixture(scope="session")
def configure_seeds(pytestconfig):
    maas_rand_seed = os.environ.get("MAAS_RAND_SEED")
    if maas_rand_seed is None:
        maas_rand_seed = time.time_ns()
    python_hash_seed = os.environ.get("PYTHONHASHSEED")
    if python_hash_seed is None:
        python_hash_seed = str(random.randint(1, 4294967295))
        os.environ["PYTHONHASHSEED"] = python_hash_seed
    pytestconfig.stash[maasseeds_stash] = str(maas_rand_seed)
    pytestconfig.stash[pythonseeds_stash] = python_hash_seed
    return maas_rand_seed, python_hash_seed


@pytest.fixture(autouse=True)
def random_seed(configure_seeds):
    maas_rand_seed, python_hash_seed = configure_seeds
    random.seed(maas_rand_seed)
    yield
