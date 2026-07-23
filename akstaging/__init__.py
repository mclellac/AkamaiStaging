VERBOSE = True
APP_NAME = "Akamai Staging"
APP_ID = "com.github.mclellac.AkamaiStaging"

import os
_build_akstaging = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "build", "akstaging"))
if os.path.exists(_build_akstaging) and _build_akstaging not in __path__:
    __path__.append(_build_akstaging)

