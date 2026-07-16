"""geotail: offline IP intelligence for your logs, powered by IP2Location LITE."""

from geotail.engine import Enricher
from geotail.models import EnrichedIP

__version__ = "0.1.0"

ATTRIBUTION = (
    "geotail uses the IP2Location LITE database for IP geolocation "
    "(https://lite.ip2location.com)."
)

__all__ = ["ATTRIBUTION", "EnrichedIP", "Enricher", "__version__"]
