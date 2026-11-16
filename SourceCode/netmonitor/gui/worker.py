"""Runs blocking service calls in a thread and hands the result back to the UI thread.

Tkinter widgets may only be touched from the main thread. Worker threads
therefore never call a widget; they put (callback, value) on a queue, and
the main thread drains that queue every few milliseconds.
"""
import queue
import threading

_results = queue.Queue()


def run_async(fn, *args, on_done=None, on_error=None):
    """Run fn(*args) in a thread, then call on_done(result) or on_error(exception) on the UI thread."""
    def task():
        try:
            _results.put((on_done, fn(*args)))
        except Exception as error:
            _results.put((on_error, error))
    threading.Thread(target=task, daemon=True).start()


def post(callback, value):
    """From any thread: have callback(value) run on the UI thread, e.g. for scan progress."""
    _results.put((callback, value))


def start_pump(root, interval_ms=50):
    """Call once from the main window. Delivers queued results on the UI thread."""
    root.after(interval_ms, start_pump, root, interval_ms)  # first, so one bad callback cannot stop the pump
    while not _results.empty():
        callback, value = _results.get()
        if callback:
            callback(value)