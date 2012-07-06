'''
@author: shylent
'''
from twisted.internet import reactor


__all__ = ['SequentialCall', 'Spent', 'Cancelled']


class Spent(Exception):
    """Trying to iterate a L{SequentialCall}, that is exhausted"""

class Cancelled(Exception):
    """Trying to iterate a L{SequentialCall}, that's been cancelled"""

def no_op(*args, **kwargs):
    pass

class SequentialCall(object):
    """Calls a given callable at intervals, specified by the L{timeout} iterable.
    Optionally calls a timeout handler, if provided, when there are no more timeout values.

    @param timeout: an iterable, that yields valid _seconds arguments to
    L{callLater<twisted.internet.interfaces.IReactorTime.callLater>} (floats)
    @type timeout: any iterable

    @param run_now: whether or not the callable should be called immediately
    upon initialization. Relinquishes control to the reactor
    (calls callLater(0,...)). Default: C{False}.
    @type run_now: C{bool}

    @param callable: the callable, that will be called at the specified intervals
    @param callable_args: the arguments to call it with
    @param callable_kwargs: the keyword arguments to call it with

    @param on_timeout: the callable, that will be called when there are no more
    timeout values
    @param on_timeout_args: the arguments to call it with
    @param on_timeout_kwargs: the keyword arguments to call it with 
    
    """

    @classmethod
    def run(cls, timeout, callable, callable_args=None, callable_kwargs=None,
                 on_timeout=None, on_timeout_args=None, on_timeout_kwargs=None,
                 run_now=False, _clock=None):
        """Create a L{SequentialCall} object and start its scheduler cycle

        @see: L{SequentialCall}

        """
        inst = cls(timeout, callable, callable_args, callable_kwargs,
                   on_timeout, on_timeout_args, on_timeout_kwargs,
                   run_now, _clock)
        inst.reschedule()
        return inst

    def __init__(self, timeout,
                 callable, callable_args=None, callable_kwargs=None,
                 on_timeout=None, on_timeout_args=None, on_timeout_kwargs=None,
                 run_now=False, _clock=None):
        self._timeout = iter(timeout)
        self.callable = callable
        self.callable_args = callable_args or []
        self.callable_kwargs = callable_kwargs or {}
        self.on_timeout = on_timeout or no_op
        self.on_timeout_args = on_timeout_args or []
        self.on_timeout_kwargs = on_timeout_kwargs or {}
        self._wd = None
        self._spent = self._cancelled = False
        self._ran_first = not run_now
        if _clock is None:
            self._clock = reactor
        else:
            self._clock = _clock

    def _call_and_schedule(self):
        self.callable(*self.callable_args, **self.callable_kwargs)
        self._ran_first = True
        if not self._spent:
            self.reschedule()

    def reschedule(self):
        """Schedule the next L{callable} call

        @raise Spent: if the timeout iterator has been exhausted and on_timeout
        handler has been already called
        @raise Cancelled: if this L{SequentialCall} has already been cancelled

        """
        if not self._ran_first:
            self._wd = self._clock.callLater(0, self._call_and_schedule)
            return
        if self._cancelled:
            raise Cancelled("This SequentialCall has already been cancelled")
        if self._spent:
            raise Spent("This SequentialCall has already timed out")
        try:
            next_timeout = self._timeout.next()
            self._wd = self._clock.callLater(next_timeout, self._call_and_schedule)
        except StopIteration:
            self.on_timeout(*self.on_timeout_args, **self.on_timeout_kwargs)
            self._spent = True

    def cancel(self):
        """Cancel the next scheduled call

        @raise Cancelled: if this SequentialCall has already been cancelled
        @raise Spent: if this SequentialCall has expired

        """
        if self._cancelled:
            raise Cancelled("This SequentialCall has already been cancelled")
        if self._spent:
            raise Spent("This SequentialCall has already timed out")
        if self._wd is not None and self._wd.active():
            self._wd.cancel()
        self._spent = self._cancelled = True

    def active(self):
        """Whether or not this L{SequentialCall} object is considered active"""
        return not (self._spent or self._cancelled)
