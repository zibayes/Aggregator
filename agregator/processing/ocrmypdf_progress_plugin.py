from ocrmypdf import hookimpl
from ocrmypdf.pluginspec import ProgressBar
from agregator.processing.ocrmypdf_progress_channel import get_queue
import logging

logger = logging.getLogger(__name__)


class MyProgressBar(ProgressBar):
    def __init__(self, *, total=None, desc=None, unit=None, disable=False, **kwargs):
        self.total = total
        self.desc = desc
        self.current = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def update(self, n=1, *, completed=None):
        if completed is not None:
            self.current = completed
        else:
            self.current += n

        total = self.total
        percent = round((self.current / total) * 100, 2) if total else 0.0
        data = {
            "desc": self.desc,
            "current": self.current,
            "total": total,
            "percent": percent,
        }
        # logger.info(f'OCRMYPDF PROGRESS: {data}')
        q = get_queue()
        if q is not None:
            q.put(data)


@hookimpl
def get_progressbar_class():
    return MyProgressBar
