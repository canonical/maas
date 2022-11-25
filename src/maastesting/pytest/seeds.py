# Copyright 2022 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).
import os
import random
import time

import pytest


@pytest.fixture(scope="session")
def configure_seeds():
    maas_rand_seed = os.environ.get("MAAS_RAND_SEED")
    if maas_rand_seed is None:
        maas_rand_seed = time.time_ns()
    python_hash_seed = os.environ.get("PYTHONHASHSEED")
    if python_hash_seed is None:
        python_hash_seed = random.randint(1, 4294967295)
        os.environ["PYTHONHASHSEED"] = str(python_hash_seed)
    return maas_rand_seed, python_hash_seed


@pytest.fixture(autouse=True)
def random_seed(configure_seeds):
    maas_rand_seed, python_hash_seed = configure_seeds
    random.seed(maas_rand_seed)
    yield
    print(
        f"MAAS_RAND_SEED={maas_rand_seed} "
        f"PYTHONHASHSEED={python_hash_seed}",
    )
