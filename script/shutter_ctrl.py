#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import urllib.request
import json
import os
import sys
import requests

sys.path.append(os.path.join(os.path.dirname(__file__), '../flask'))
from config import CONTROL_ENDPOONT

def set_shutter_state(mode):
    try:
        req = urllib.request.Request('{}?{}'.format(
            CONTROL_ENDPOONT['api']['ctrl'], urllib.parse.urlencode({
                'set': mode,
                'auto': 1,
            }))
        )
        status = json.loads(urllib.request.urlopen(req).read().decode())
        return status['result'] == 'success'
    except:
        pass

    return False


if __name__ == '__main__':
    mode = sys.argv[1]
    set_shutter_state(mode)
