# import_export_openreplay/controllers.py
# Brought to you by We Vote. Be good.
# -*- coding: UTF-8 -*-

from config.environment_variable_functions import get_environment_variable
import wevote_functions.admin


logger = wevote_functions.admin.get_logger(__name__)

OPENREPLAY_BASE_URL = get_environment_variable("OPENREPLAY_BASE_URL", no_exception=True)
OPENREPLAY_PROJECT_KEY = get_environment_variable("OPENREPLAY_PROJECT_KEY", no_exception=True)
OPENREPLAY_ORGANIZATION_KEY = get_environment_variable("OPENREPLAY_ORGANIZATION_KEY", no_exception=True)



