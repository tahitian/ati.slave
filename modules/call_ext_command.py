#!/usr/bin/python

import subprocess

def call_ext_sync(command):
    process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = process.communicate()
    errcode = process.returncode
    if errcode != 0:
        return False, err.strip()
    else:
        return True, out.strip()

def call_ext_async(command):
    process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return process

if __name__ == '__main__':
    command = "ping www.baidu.com -c 4"
    print "# call_ext_sync"
    (code, out) = call_ext_sync(command)
    print "# code: %d, out: %s" % (code, out)
    print "################"
    print "# call_ext_async"
    process = call_ext_async(command)
    while True:
        line = process.stdout.readline()
        if not line:
            break
        print line.strip()
    code = process.returncode
    print "# code: %d" % (code)
