from contextlib import contextmanager
from cProfile import Profile
from typing import Optional


@contextmanager
def profiler(filename: Optional[str] = None, sort: str = "calls"):
    """Context manager to profile a code section in tests.

    if `filename` is provided, dump the profiler output to file, otherwise
    print stats to stdout.
    """
    profile = Profile()
    profile.enable()
    yield profile
    profile.create_stats()
    if filename:
        profile.dump_stats(filename)
    else:
        print()
        profile.print_stats(sort=sort)
