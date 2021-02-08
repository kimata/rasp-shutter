#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from flask import (
    request, jsonify, current_app, Response, send_from_directory,
    after_this_request,
    Blueprint
)

from functools import wraps
import re
import socket
import sqlite3
import subprocess
import threading
import time
import pathlib
import json
from crontab import CronTab
import os
import functools
import requests
import gzip
from io import BytesIO

from config import CONTROL_ENDPOONT

APP_PATH = '/rasp-shutter'
VUE_DIST_PATH = '../dist'

SCHEDULE_MARKER = 'SHUTTER SCHEDULE'

EXE_HIST_FILE_FORMAT = '/dev/shm/shutter_hist_{mode}'

EVENT_TYPE_MANUAL = 'manual'
EVENT_TYPE_LOG = 'log'
EVENT_TYPE_SCHEDULE = 'schedule'

event_count = {
    EVENT_TYPE_MANUAL: 0,
    EVENT_TYPE_LOG: 0,
    EVENT_TYPE_SCHEDULE: 0,
}

SHUTTER_CTRL_CMD = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', 'script', 'shutter_ctrl.py')
)

rasp_shutter = Blueprint('rasp-shutter', __name__, url_prefix=APP_PATH)

sqlite = sqlite3.connect(':memory:', check_same_thread=False)
sqlite.execute('CREATE TABLE log(date INT, message TEXT)')
sqlite.row_factory = lambda c, r: dict(
    zip([col[0] for col in c.description], r)
)

schedule_lock = threading.Lock()
event_lock = threading.Lock()

SCHEDULE_MARKER = 'SHUTTER SCHEDULE'
SHUTTER_CTRL_CMD = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', 'script', 'shutter_ctrl.py')
)

def parse_cron_line(line):
    match = re.compile(
        '^(#?)\s*(\@daily|(?:(\d{{1,2}})\s+(\d{{1,2}}))).+{}'.format(
            re.escape(SHUTTER_CTRL_CMD)
        )
    ).search(str(line))

    if match:
        mg = match.groups()
        is_active = mg[0] == ''
        if (mg[1] == '@daily'):
            time = '00:00'
        else:
            time = '{:02}:{:02}'.format(int(mg[3]), int(mg[2]))
        return {
            'is_active': is_active,
            'time': time,
        }
    return None


def cron_read():
    cron = CronTab(user=True)
    schedule = {}
    for mode in ['open', 'close']:
        item = None
        try:
            item = parse_cron_line(
                next(cron.find_comment('{} ({})'.format(SCHEDULE_MARKER, mode)))
            )
        except:
            pass
        if (item is None):
            item = {
                'is_active': False,
                'time': '00:00',
            }
        schedule[mode] = item

    return schedule

def cron_create_job(cron, schedule, mode):
    job = cron.new(
        command='{} {}'.format(SHUTTER_CTRL_CMD, mode)
    )
    time = schedule[mode]['time'].split(':')
    time.reverse()
    job.setall('{} {} * * *'.format(*time))
    job.set_comment('{} ({})'.format(SCHEDULE_MARKER, mode))
    job.enable(schedule[mode]['is_active'])

    return job


def cron_write(schedule):
    cron = CronTab(user=True)
    new_cron = CronTab()

    # NOTE: remove* 系のメソッドを使うとどんどん空行が増えるので，
    # append して更新を行う．

    for job in cron:
        for mode in ['open', 'close']:
            if re.compile(
                    '{} \({}\)'.format(re.escape(SCHEDULE_MARKER), mode)
            ).search(job.comment):
                job = cron_create_job(cron, schedule, mode)
                schedule[mode]['append'] = True
        # NOTE: Ubuntu の場合 apt でインストールした python-crontab
        # では動かない．pip3 でインストールした python-crontab が必要．
        new_cron.append(job)

    for mode in ['open', 'close']:
        if ('append' not in schedule[mode]):
            new_cron.append(cron_create_job(cron, schedule, mode))

    new_cron.write_to_user(user=True)

    # すぐに反映されるよう，明示的にリロード
    subprocess.check_call(['sudo', '/etc/init.d/cron', 'restart'])


# auto = 0: 手動, 1: 自動(実際には制御しなかった場合にメッセージ有り), 2: 自動
def set_shutter_state(mode, auto, host):
    result = True

    exe_hist = pathlib.Path(EXE_HIST_FILE_FORMAT.format(mode=mode))
    if (auto > 0):
        if (exe_hist.exists() and
            ((time.time() - exe_hist.stat().st_mtime) / (60 * 60) < 24)):
            if (auto == 1):
                log('シャッターを自動で{done}るのを見合わせました。{by}'.format(
                    done='開け' if mode == 'open' else '閉め',
                    by='(by {})'.format(host) if host != '' else ''
                ))
            return True
    exe_hist.touch()
    inv_hist = pathlib.Path(EXE_HIST_FILE_FORMAT.format(mode='close' if mode == 'open' else 'open'))
    inv_hist.unlink(missing_ok=True)

    for endpoint in CONTROL_ENDPOONT[mode]:
        if (requests.get(endpoint).status_code != 200):
            result = False

    if result:
        log('シャッターを{auto}で{done}ました。{by}'.format(
            auto='自動' if auto > 0 else '手動',
            done='開け' if mode == 'open' else '閉め',
            by='(by {})'.format(host) if host != '' else ''
        ))
    else:
        log('シャッターを{auto}で{done}るのに失敗しました。{by}'.format(
            auto='自動' if auto > 0 else '手動',
            done='開け' if mode == 'open' else '閉め',
            by='(by {})'.format(host) if host != '' else ''
        ))

    return result


def log_message(message, host):
    result = True
    log(message)

    return result


def schedule_entry_str(mode, entry):
    return '{} {}'.format(
        entry['time'], mode.upper()
    )


def schedule_str(schedule):
    str = []
    for mode in ['open', 'close']:
        entry = schedule[mode]
        if not entry['is_active']:
            continue
        str.append(schedule_entry_str(mode, entry))

    return ', '.join(str)


def log_impl(message):
    global event_count
    with event_lock:
        sqlite.execute(
            'INSERT INTO log ' +
            'VALUES (DATETIME("now", "localtime"), ?)',
            [message]
        )
        sqlite.execute(
            'DELETE FROM log ' +
            'WHERE date <= DATETIME("now", "localtime", "-60 days")'
        )
        event_count[EVENT_TYPE_LOG] += 1


def log(message):
    threading.Thread(target=log_impl, args=(message,)).start()


def gzipped(f):
    @functools.wraps(f)
    def view_func(*args, **kwargs):
        @after_this_request
        def zipper(response):
            accept_encoding = request.headers.get('Accept-Encoding', '')

            if 'gzip' not in accept_encoding.lower():
                return response

            response.direct_passthrough = False

            if (response.status_code < 200 or
                response.status_code >= 300 or
                'Content-Encoding' in response.headers):
                return response
            gzip_buffer = BytesIO()
            gzip_file = gzip.GzipFile(mode='wb',
                                      fileobj=gzip_buffer)
            gzip_file.write(response.data)
            gzip_file.close()

            response.data = gzip_buffer.getvalue()
            response.headers['Content-Encoding'] = 'gzip'
            response.headers['Vary'] = 'Accept-Encoding'
            response.headers['Content-Length'] = len(response.data)
            response.headers['Cache-Control'] = 'max-age=31536000'
            response.add_etag()

            return response

        return f(*args, **kwargs)

    return view_func


def support_jsonp(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        callback = request.args.get('callback', False)
        if callback:
            content = callback + '(' + f().data.decode() + ')'
        else:
            content = f().data

        response = current_app.response_class(
            content, mimetype='application/json'
        )
        response.headers['Access-Control-Allow-Origin'] = '*'
        return response

    return decorated_function


def remote_host(request):
    try:
        return socket.gethostbyaddr(request.remote_addr)[0]
    except:
        return request.remote_addr


@rasp_shutter.route('/api/shutter_ctrl', methods=['GET', 'POST'])
@support_jsonp
def api_shutter_ctrl():
    is_success = False
    state = request.args.get('set', 'none', type=str)
    auto = request.args.get('auto', 0, type=int)

    if state != 'none':
        is_success = set_shutter_state(state, auto, remote_host(request))

    return jsonify({ 'result': is_success })


@rasp_shutter.route('/api/log_ctrl', methods=['GET', 'POST'])
@support_jsonp
def api_log_message():
    is_success = False
    message = request.args.get('message', '', type=str)

    is_success = log_message(message, remote_host(request))

    return jsonify({ 'result': is_success })


@rasp_shutter.route('/api/schedule_ctrl', methods=['GET', 'POST'])
@support_jsonp
def api_schedule_ctrl():
    state = request.args.get('set', None)
        
    if (state is not None):
        with schedule_lock:
            schedule = json.loads(state)
            cron_write(schedule)

            host=remote_host(request)
            log('スケジュールを更新しました。\n({schedule} {by})'.format(
                schedule=schedule_str(schedule),
                by='by {}'.format(host) if host != '' else ''
            ))

    return jsonify(cron_read())


@rasp_shutter.route('/api/log', methods=['GET'])
@support_jsonp
def api_log():
    cur = sqlite.cursor()
    cur.execute('SELECT * FROM log')
    return jsonify({
        'data': cur.fetchall()[::-1]
    })


@rasp_shutter.route('/api/event', methods=['GET'])
def api_event():
    def event_stream():
        last_count = event_count.copy()
        while True:
            time.sleep(0.3)
            for method in last_count:
                if (last_count[method] != event_count[method]):
                    yield "data: {}\n\n".format(method)
                    last_count[method] = event_count[method]

    res = Response(event_stream(), mimetype='text/event-stream')
    res.headers.add('Access-Control-Allow-Origin', '*')
    res.headers.add('Cache-Control', 'no-cache')

    return res


@rasp_shutter.route('/', defaults={'filename': 'index.html'})
@rasp_shutter.route('/<path:filename>')
@gzipped
def vue(filename):
    return send_from_directory(VUE_DIST_PATH, filename)
