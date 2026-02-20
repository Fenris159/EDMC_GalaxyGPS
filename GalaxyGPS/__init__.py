# _plugin_tl is set by load.py before this package is executed (EDMC PLUGINS.md: avoid
# "from load import" so the name "load" is not shared across plugins). Submodules use
# "from GalaxyGPS import _plugin_tl".
import sys
import traceback
from .updater import SpanshUpdater
from .AutoCompleter import AutoCompleter
from .PlaceHolder import PlaceHolder
from .FleetCarrierManager import FleetCarrierManager
from .GalaxyGPS import GalaxyGPS