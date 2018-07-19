#!/usr/bin/env python

import fcntl
import json
import numpy
import os
import pycurl
import Queue
import select
import signal
import socket
import sys
import threading
import time
import urllib
if not (sys.path[0] + "/modules") in sys.path:
    sys.path.append(sys.path[0] + "/modules")
import console
import curl_methods
import pptp
from call_ext_command import *
from wait import wait

def init_log(name):
    log_dir = "/var/log/ati/"
    log_file = log_dir + name + ".log"
    if not os.path.exists(log_dir):
        os.mkdir(log_dir)
    elif not os.path.isdir(log_dir):
        sys.stderr.write("critical: unable to initialize log file, exit...\n")
        return False
    console.init(name, log_file)
    return True

def handler(signum, frame):
    global g_stop_loop
    g_stop_loop = True

def get_system_uuid():
    uuid = None
    command = "dmidecode -s system-uuid"
    ok, output = call_ext_sync(command)
    if ok:
        uuid = output
    return uuid

def run_routine_in_thread(routine):
    thread = None
    target = routine["target"]
    arguments = routine["arguments"]
    thread = threading.Thread(target = target, args = arguments)
    thread.setDaemon(True)
    thread.start()
    return thread

def track_task(taskinfo):
    api_url = "http://172.16.26.112:37000/api/track/slave/%s" % str(taskinfo)
    code, html = curl_methods.curl_get(api_url)
    return (code == 200)

def track_task_by_unit_id(unit_id, imp, clk):
    url = 'http://172.16.47.210:80/track/detail'
    post_data = {
        'client_id': 'test',
        'unit_id': unit_id,
        'detail': {
            'imp': imp,
            'clk': clk
        }
    }
    data = json.dumps(post_data)
    options = {}
    options[pycurl.POSTFIELDS] = data
    options[pycurl.HTTPHEADER] = ['Content-Type: application/json']
    code, html = curl_methods.curl_get(url, options)

class task_manager:
    uuid = get_system_uuid()
    def __init__(self, capacity):
        self.tasks = []
        self.threads = []
        self.capacity = capacity
        self.backlog = Queue.Queue()

    def receive_tasks(self):
        while len(self.tasks) < self.capacity:
            # backlog
            message = None
            try:
                message = self.backlog.get(block = False)
            except Exception, e:
                pass
            # fresh message
            if not message:
                #to do@jiangtu api_url
                api_url = "http://172.16.47.210:80/get_task/bidding?client_id=test&task_type=0"
                code, html = curl_methods.curl_get(api_url)
                if code == 200:
                    try:
                        message = json.loads(html.strip())["task"]
                    except Exception, e:
                        console.log.warning("%r %r" % (e, html))
            if not message:
                break
            self.tasks.append(message)

    def execute_tasks(self):
        while len(self.tasks):
            task = self.tasks.pop(0)
            routine = {
                "target": self.run_task,
                "arguments": (task, )
            }
            thread = run_routine_in_thread(routine)
            self.threads.append(thread)

    def run_task(self, task):
        success = False
        fakeloop = True
        state = ""
        while fakeloop:
            try:
                imp = str(task["imp"])
                ua = str.strip(str(task["ua"]))
                headers = task["headers"]
                cookie_file = "%s/runtime/cookies/ati_slave.%d" % (sys.path[0], threading.current_thread().ident)
                options = {}
                options[pycurl.USERAGENT] = ua
                options[pycurl.COOKIEJAR] = cookie_file
                if "referrer" in headers and headers["referrer"]:
                    options[pycurl.REFERER] = str(headers["referrer"])
                code, html = curl_methods.curl_get(imp, options)
                if code != 200 and code != 302:
                    break
                clk = str(task["clk"])
                if clk:
                    delay = 1 + min(3 ** numpy.random.normal(), 10)
                    time.sleep(delay)
                    options = {}
                    options[pycurl.USERAGENT] = ua
                    options[pycurl.COOKIEFILE] = cookie_file
                    code, html = curl_methods.curl_get(clk, options)
                    if code != 200 and code != 302:
                        break
                success = True
            except Exception, e:
                console.log.warning("%r" % e)
                break
            fakeloop = False
        else:
            # ok
            state = "pass"
            pass
        if not success:
            # todo: task fail
            self.backlog.put(task)
            state = "fail"
            pass
        taskinfo = "name=%s&imp=%d&clk=%d&slave=%s&state=%s" % (str(task["task_id"]), 1 if str(task["imp"]) else 0, 1 if str(task["clk"]) else 0, self.uuid, state)
        track_task(taskinfo)
        if state == "pass":
            imp_status = 1
            clk_status = 1 if clk else 0
            track_task_by_unit_id(task["unit_id"], imp_status, clk_status)
        current_thread = threading.current_thread()
        if current_thread in self.threads:
            self.threads.remove(current_thread)

    def __del__(self):
        pass

def get_pptp_route_targets():
    targets = None
    api_url = "http://172.16.26.112:37000/api/pptp/route_targets"
    code, html = curl_methods.curl_get(api_url)
    if code == 200:
        try:
            targets = json.loads(html.strip())
        except Exception, e:
            console.log.warning("%r" % e)
    return targets

def resolve_domain(domain):
    address = None
    command = "dig A +short %s" % domain
    ok, output = call_ext_sync(command)
    if ok:
        address = output.strip()
    return address

def get_pptp_account(key, uuid):
    account = {}
    api_url = "http://172.16.26.112:37000/api/pptp/account/%s/%s" % (key, uuid)
    code, html = curl_methods.curl_get(api_url)
    if code == 200:
        try:
            account = json.loads(html.strip())
        except Exception, e:
            console.log.warning("%r" % e)
    return account

def track_pptp(pptpinfo):
    api_url = "http://172.16.26.112:37000/api/pptp/track/%s" % str(pptpinfo)
    code, html = curl_methods.curl_get(api_url)

class pptp_manager():
    uuid = get_system_uuid()
    def __init__(self, key):
        self.stop = False
        self.key = key
        self.name = "slave_" + key
        self.target_addresses = []
        self.update_route_addresses_in_cycle(60.0)
        self.account = None
        self.pptp = None

    def update_route_addresses_in_cycle(self, interval):
        addresses = []
        targets = get_pptp_route_targets()
        for target in targets:
            if target["type"] == "domain":
                address = resolve_domain(str(target["value"]))
                if not address:
                    console.log.warning("failed to resolve domain: \"%s\"" % (str(target["value"]), ))
                else:
                    addresses.append(address)
            elif target["type"] == "address":
                addresses.append(str(target["value"]))
        self.target_addresses = addresses
        if not self.stop:
            thread = threading.Timer(interval, self.update_route_addresses_in_cycle, (interval, ))
            thread.setDaemon(True)
            thread.start()

    def update_pptp_account(self):
        done = False
        account = get_pptp_account(self.key, self.uuid)
        if cmp(self.account, account):
            self.account = account
        if self.account:
            server = str(self.account["server"])
            mppe = int(self.account["mppe"])
            username = str(self.account["username"])
            password = str(self.account["password"])
            console.log.info("pptp account updated: %s, %s, %s" % (server, username, password))
            if self.pptp:
                self.pptp.stop()
                self.pptp.delete()
            self.pptp = pptp.pptp(self.name, server, username, password, mppe)
            self.pptp.create()
            done = True
        return done

    def start_pptp_link(self):
        pptp_begin_ts = time.time()
        ok = self.pptp.start()
        pptp_finish_ts = time.time()
        pptp_duration = int(pptp_finish_ts - pptp_begin_ts)
        pptpinfo = "server=%s&username=%s&state=%s&duration=%d" % (str(self.account["server"]), str(self.account["username"]), "ok" if ok else "error", pptp_duration)
        track_pptp(pptpinfo)
        return ok

    def stop_pptp_link(self):
        done = True
        if self.pptp:
            done = self.pptp.stop()
        return done

    def set_route(self):
        done = False
        command_template = "ip route add %s dev ppp0"
        for address in self.target_addresses:
            ok, output = call_ext_sync(command_template % (address, ))
            if not ok:
                console.log.warning("failed to set route for %s" % (address, ))
            else:
                done = True
        return done

    def check_route(self):
        ok = False
        pass_count = 0
        command_template = "ip route|grep \"%s\""
        for address in self.target_addresses:
            retry = 0
            delay = 0.05
            while retry < 3:
                ok, output = call_ext_sync(command_template % (address, ))
                if ok:
                    if output.find("dev ppp0") > -1:
                        pass_count += 1
                        break
                    else:
                        console.log.warning("no route via pptp for %s" % address)
                else:
                    console.log.warning("failed to check route for %s" % (address, ))
                retry += 1
                time.sleep(delay)
        if pass_count == len(self.target_addresses):
            ok = True
        return ok

    def __del__(self):
        self.stop = True

def start():
    global g_stop_loop
    console.log.info("application started...");
    # tasks
    capacity = 70
    tm = task_manager(capacity)
    thread_gap = wait(1, 8)
    task_gap = wait(1, 8)
    task_ready = False
    # pptp
    pm = pptp_manager("default")
    pptp_account_gap = wait(1, 8)
    pptp_account_ready = False
    pptp_link_gap = wait(1, 8)
    pptp_link_ready = False
    pptp_route_gap = wait(1, 8)
    pptp_route_ready = False
    while not g_stop_loop:
        if len(tm.threads) > 0:
            console.log.debug("there has running task not finished, waiting...")
            thread_gap.wait()
            continue
        thread_gap.reset()
        if not task_ready:
            tm.receive_tasks()
            if len(tm.tasks) == 0:
                console.log.debug("no task right now, waiting...")
                task_gap.wait()
                continue
            task_ready = True
            pm.stop_pptp_link()
            pptp_account_ready = False
            task_gap.reset()
        if not pptp_account_ready:
            ok = pm.update_pptp_account()
            if not ok:
                console.log.debug("no pptp account, waiting...")
                pptp_account_gap.wait()
                continue
            pptp_account_ready = True
            pptp_link_ready = False
            pptp_account_gap.reset()
        if not pptp_link_ready:
            ok = pm.start_pptp_link()
            if not ok:
                console.log.debug("no pptp link, waiting...")
                pptp_link_gap.wait()
                if pptp_link_gap.count > 3:
                    pptp_account_ready = False
                continue
            pptp_link_ready = True
            pptp_route_ready = False
            pptp_link_gap.reset()
        if not pptp_route_ready:
            ok = pm.set_route()
            if ok:
                ok = pm.check_route()
                if not ok:
                    console.log.debug("no route via pptp, waiting...")
                    pptp_route_gap.wait()
                    continue
            pptp_route_ready = True
            pptp_route_gap.reset()
        tm.execute_tasks()
        task_ready = False
    console.log.info("application stopped...")

def main():
    init_log("new_slave")
    signal.signal(signal.SIGINT, handler)
    signal.signal(signal.SIGTERM, handler)
    start()

if __name__ == '__main__':
    g_stop_loop = False
    main()
    sys.exit(0)
