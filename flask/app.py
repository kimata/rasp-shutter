#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import datetime

from flask import Flask

from rasp_shutter import rasp_shutter

app = Flask(__name__)

app.register_blueprint(rasp_shutter)

if __name__ == '__main__':
    app.debug = True
    app.run(host='0.0.0.0', threaded=True)
