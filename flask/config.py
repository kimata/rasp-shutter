CONTROL_ENDPOONT = {
    'api': {
        'ctrl': 'http://192.168.0.18:5000/rasp-shutter/api/shutter_ctrl',
        'log': 'http://192.168.0.18:5000/rasp-shutter/api/log_ctrl',
    },
    'open': [
        'http://192.168.0.80/api/32',
        'http://192.168.0.81/api/32'
    ],
    'close': [
        'http://192.168.0.80/api/33',
        'http://192.168.0.81/api/33'
    ]
}

LOG_DATABASE = '/dev/shm/shutter_log.db'

EXE_HIST_FILE_FORMAT = '/dev/shm/shutter_hist_{mode}'
EXE_RESV_FILE_FORMAT = '/dev/shm/shutter_resv_{mode}'
