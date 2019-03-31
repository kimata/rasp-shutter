#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import requests

sys.path.append(os.path.join(os.path.dirname(__file__), '../flask'))
from config import CONTROL_ENDPOONT

def set_shutter_state(mode):
    result = True
    for endpoint in CONTROL_ENDPOONT[mode]:
        if (requests.get(endpoint).status_code != 200):
            result = False

    return result


if __name__ == '__main__':
    mode = sys.argv[1]
    set_shutter_state(mode)


