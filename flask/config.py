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
