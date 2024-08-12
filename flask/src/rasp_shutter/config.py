#!/usr/bin/env python3

import my_lib.webapp.config

STAT_EXEC_TMPL = {
    "open": my_lib.webapp.config.STAT_DIR_PATH / "exe" / "{index}_open",
    "close": my_lib.webapp.config.STAT_DIR_PATH / "exe" / "{index}_close",
}

STAT_PENDING_OPEN = my_lib.webapp.config.STAT_DIR_PATH / "pending" / "open"
STAT_AUTO_CLOSE = my_lib.webapp.config.STAT_DIR_PATH / "auto" / "close"

# この時間内では自動制御で開閉しない．
EXEC_INTERVAL_AUTO_MIN = 2
