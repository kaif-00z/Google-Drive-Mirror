from libs.tracker.downloads import DownloadTracker, Algorithms
from libs.tracker.users import UserTracker, Activities

class Tracker:
    def __init__(self):
        self._dl_t = DownloadTracker()
        self._u_t = UserTracker()

    async def wake(self):
        await self._dl_t.init_db()
        await self._u_t.init_db()

    @property
    def user(self) -> UserTracker:
        return self._u_t
    
    @property
    def dl(self) -> DownloadTracker:
        return self._dl_t