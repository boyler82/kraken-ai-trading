"""Conservative cross-asset time grouping, not proof of independence."""
from datetime import timedelta
from .schemas import utc
METHOD = 'GLOBAL_24H_UTC_V1'

def cluster(timestamp, shifted=False):
    if timestamp is None:
        return None
    t = utc(timestamp) - (timedelta(hours=12) if shifted else timedelta())
    return ('GLOBAL_24H_SHIFT12_V1:' if shifted else METHOD + ':') + t.date().isoformat()
