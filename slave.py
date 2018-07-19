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
if not (sys.path[0] + "/modules") in sys.path:
    sys.path.append(sys.path[0] + "/modules")
import console
import curl_methods
import pptp
import rabbitmq
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

# def run_routine_in_thread(routine):
#     thread = None
#     target = routine["target"]
#     arguments = routine["arguments"]
#     thread = threading.Thread(target = target, args = arguments)
#     thread.setDaemon(True)
#     thread.start()
#     return thread

# def track_task(taskinfo):
#     api_url = "http://172.16.26.112:37000/api/track/slave/%s" % str(taskinfo)
#     code, html = curl_methods.curl_get(api_url)
#     return (code == 200)

class task_manager:
    uuid = get_system_uuid()
    def __init__(self, capacity, mq_name):
        pass

    def run_task(self):
        success = False
        fakeloop = True
        state = ""
        while fakeloop:
            try:
                # imp = str(task["imp"])
                # ua = str(task["ua"])
                imp = 'http://182.254.156.102'
                headers = task["headers"]
                cookie_file = "%s/runtime/cookies/ati_slave.%d" % (sys.path[0], threading.current_thread().ident)
                options = {}
                # options[pycurl.USERAGENT] = ua
                options[pycurl.COOKIEJAR] = cookie_file
                if "referrer" in headers and headers["referrer"]:
                    options[pycurl.REFERER] = str(headers["referrer"])
                code, html = curl_methods.curl_get(imp, options)
                if code != 200 and code != 302:
                    print('fail')
                    break
                success = True
                print('success')
            except Exception, e:
                print("%r" % e)
                print('fail')
                break
            fakeloop = False

    def __del__(self):
        self.mq.disconnect()

class pptp_manager():
    uuid = get_system_uuid()
    def __init__(self, key):
        self.stop = False
        self.key = key
        self.name = "slave_" + key
        # self.target_addresses = []
        # self.update_route_addresses_in_cycle(60.0)
        self.account = None
        self.pptp = None

    def update_pptp_account(self):
        done = False
        # account = get_pptp_account(self.key, self.uuid)
        # if cmp(self.account, account):
        #     self.account = account
        # if self.account:
        server = 'shh.91ip.vip'
        mppe = None
        username = 'gm49'
        password = '111'
        if self.pptp:
            self.pptp.stop()
            self.pptp.delete()
        self.pptp = pptp.pptp(self.name, server, username, password, mppe)
        self.pptp.create()
        done = True
        return done

    def start_pptp_link(self):
        # pptp_begin_ts = time.time()
        ok = self.pptp.start()
        # pptp_finish_ts = time.time()
        # pptp_duration = int(pptp_finish_ts - pptp_begin_ts)
        # pptpinfo = "server=%s&username=%s&state=%s&duration=%d" % (str(self.account["server"]), str(self.account["username"]), "ok" if ok else "error", pptp_duration)
        # track_pptp(pptpinfo)
        return ok

    def stop_pptp_link(self):
        done = True
        if self.pptp:
            done = self.pptp.stop()
        return done

    def set_route(self):
        done = False
        command_template = "ip route add %s dev ppp0"
        # for address in self.target_addresses:
        address = '182.254.156.102'
        ok, output = call_ext_sync(command_template % (address, ))
        if not ok:
            print("failed to set route for %s" % (address, ))
        else:
            done = True
        return done

    def check_route(self):
        ok = False
        pass_count = 0
        command_template = "ip route|grep \"%s\""
        # for address in self.target_addresses:
        address = '182.254.156.102'
        retry = 0
        delay = 0.05
        while retry < 3:
            ok, output = call_ext_sync(command_template % (address, ))
            if ok:
                if output.find("dev ppp0") > -1:
                    pass_count += 1
                    break
                else:
                    print("no route via pptp for %s" % address)
            else:
                print("failed to check route for %s" % (address, ))
            retry += 1
            time.sleep(delay)
        if pass_count == 1:
            ok = True
        return ok

    def __del__(self):
        self.stop = True

def start():
    global g_stop_loop
    console.log.info("application started...");
    # tasks
    capacity = 90
    queue_name = "ATI"
    tm = task_manager(capacity, queue_name)
    # thread_gap = wait(1, 8)
    # task_gap = wait(1, 8)
    # task_ready = False
    # pptp
    pm = pptp_manager("default")
    pptp_account_gap = wait(1, 8)
    pptp_account_ready = False
    pptp_link_gap = wait(1, 8)
    pptp_link_ready = False
    pptp_route_gap = wait(1, 8)
    pptp_route_ready = False

    while not pptp_account_ready:
        ok = pm.update_pptp_account()
        if not ok:
            print("no pptp account, waiting...")
            # pptp_account_gap.wait()
            continue
        pptp_account_ready = True

    i = 100
    while i>0:
        i -= 1
        if not pptp_link_ready:
            ok = pm.start_pptp_link()
            if not ok:
                print("no pptp link, waiting...")
                # pptp_link_gap.wait()
                # if pptp_link_gap.count > 3:
                #     pptp_account_ready = False
                continue
            pptp_link_ready = True
            pptp_route_ready = False
            # pptp_link_gap.reset()
        if not pptp_route_ready:
            ok = pm.set_route()
            if not ok:
                print("no route via pptp, waiting...")
                continue
            if ok:
                ok = pm.check_route()
                if not ok:
                    print("no route via pptp, waiting...")
                    # pptp_route_gap.wait()
                    continue
            pptp_route_ready = True
            # pptp_route_gap.reset()
        tm.run_task()
        pptp_link_ready = False
    console.log.info("application stopped...")

def main():
    init_log("slave")
    signal.signal(signal.SIGINT, handler)
    signal.signal(signal.SIGTERM, handler)
    start()

if __name__ == '__main__':
    g_stop_loop = False
    main()
    sys.exit(0)
