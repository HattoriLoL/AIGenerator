"""The stages declare what they read from and write to the job (t, from generate.py), and a sequence is checked before
it runs.

    @stages.declare(reads=("request", "sheet"), writes=("positive", "negative"))
    def stage(t): ...

`check(sequence)` walks the stages in order and refuses (SequenceError) one that has no declaration and one that reads
a value that neither the BASE (what the Job carries from the start) nor an earlier stage writes: a wrong sequence stops
before anything is loaded on the GPU.

Pure module (standard library only): the tests import it without torch.
"""
import os

# what the Job carries from the start (generate.Job.__init__)
BASE = frozenset(("request", "output", "session", "cfg", "t_start", "timings"))


class SequenceError(Exception):
    """A stage sequence that does not hold together: a stage without a declaration, or one that reads what no earlier
    stage wrote."""


def declare(reads=(), writes=()):
    """Sets the f.reads and f.writes sets on f and returns the same function."""
    def mark(f):
        f.reads, f.writes = frozenset(reads), frozenset(writes)
        return f
    return mark


def name(f):
    """'<file without .py>.<function>': from the file, not from __module__, which is '__main__' when run with -m."""
    return "%s.%s" % (os.path.splitext(os.path.basename(f.__code__.co_filename))[0], f.__name__)


def check(sequence):
    """Refuses a sequence that does not hold together, with the stage and value names in the message; runs no stage."""
    written = set(BASE)
    for f in sequence:
        if not (hasattr(f, "reads") and hasattr(f, "writes")):
            raise SequenceError("the stage '%s' does not declare what it reads and writes" % name(f))
        missing = sorted(f.reads - written)
        if missing:
            raise SequenceError("invalid stage sequence: the stage '%s' reads '%s', which no earlier stage writes"
                                % (name(f), missing[0]))
        written |= f.writes
