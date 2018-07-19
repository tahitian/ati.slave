import fcntl
import os
import select

import console
from call_ext_command import *

class pptp:
    def __init__(self, name, server, username, password, mppe):
        self.name = name
        self.server = server
        self.username = username
        self.password = password
        self.mppe = mppe

    def create(self):
        command = "/usr/sbin/pptpsetup --create \"%s\" --server \"%s\" --username \"%s\" --password \"%s\" %s" % (self.name, self.server, self.username, self.password, "--encrypt" if self.mppe else "")
        ok, output = call_ext_sync(command)
        return ok

    def delete(self):
        command = "/usr/sbin/pptpsetup --delete %s" % self.name
        ok, output = call_ext_sync(command)
        return ok

    def start(self):
        command = "/usr/sbin/pon %s nodetach" % self.name
        process = call_ext_async(command)
        stdout_fd = process.stdout.fileno()
        fl = fcntl.fcntl(stdout_fd, fcntl.F_GETFL)
        fcntl.fcntl(stdout_fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)
        epoll = select.epoll()
        epoll.register(stdout_fd, select.EPOLLIN)
        timeout = 1
        retry = 0
        done = False
        ok = False
        while not done:
            events = epoll.poll(timeout)
            if not events:
                retry += 1
                if retry > 10:
                    done = True
                continue
            for fd, event in events:
                if fd != stdout_fd:
                    console.log.warning("this should not happen")
                    done = True
                    continue
                if event == select.EPOLLHUP:
                    done = True
                    break
                elif event == select.EPOLLIN:
                    line = process.stdout.readline()
                    if not line:
                        console.log.warning("nothing read")
                        continue
                    line = line.strip()
                    console.log.debug(line)
                    if line.find("MS-CHAP authentication failed") > -1:
                        done = True
                    elif line.find("authentication failed") > -1:
                        done = True
                    elif line.find("HOST NOT FOUND") > -1:
                        done = True
                    elif line.find("Call manager exited with error") > -1:
                        done = True
                    elif line.find("Modem hangup") > -1:
                        done = True
                    elif line.find("Connection refused") > -1:
                        done = True
                    elif line.find("CHAP authentication succeeded") > -1:
                        pass
                    elif line.find("local  IP address ") > -1:
                        pass
                    elif line.find("remote IP address ") > -1:
                        ok = True
                        done = True
        if not ok:
            self.stop()
        return ok

    def stop(self):
        command = "/usr/sbin/poff -a %s" % self.name
        ok, output = call_ext_sync(command)
        return ok

    def __del__(self):
        self.delete()
