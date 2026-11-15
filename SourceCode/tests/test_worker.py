"""Tests for gui/worker.py (results travel from a thread to the UI thread)."""
import time

from netmonitor.gui import worker


class FakeRoot:
    def after(self, *args):
        pass


def test_result_and_error_are_delivered_by_the_pump():
    got = []
    worker.run_async(lambda a, b: a + b, 2, 3, on_done=got.append)
    worker.run_async(lambda: 1 / 0, on_error=got.append)
    worker.post(got.append, "progress")
    time.sleep(0.2)
    assert got == []                      # nothing is delivered off the UI thread
    worker.start_pump(FakeRoot())
    assert 5 in got and "progress" in got
    assert any(isinstance(item, ZeroDivisionError) for item in got)