import logging
import logging.handlers
import sys

log = None

def init(name, file):
    global log
    log = logging.getLogger(name)
    formatter = logging.Formatter("[%(name)s] [%(asctime)s] [%(levelname)s] [%(filename)s:%(lineno)d %(funcName)s()] \"%(message)s\"")
    filehandler = logging.handlers.RotatingFileHandler(file, mode = "a", maxBytes = 1073741824, backupCount = 4)
    filehandler.setFormatter(formatter)
    streamhandler = logging.StreamHandler(sys.stdout)
    streamhandler.setFormatter(formatter)
    log.addHandler(filehandler)
    log.addHandler(streamhandler)
    log.setLevel(logging.DEBUG)

def setLevel(level):
    global log
    if not log:
        return
    log.setLevel(logging.DEBUG)
    log.info("log level set to %s" % (level))
    if level == "DEBUG":
        log.setLevel(logging.DEBUG)
    elif level == "INFO":
        log.setLevel(logging.INFO)
    elif level == "WARNING":
        log.setLevel(logging.WARNING)
    elif level == "ERROR":
        log.setLevel(logging.ERROR)
    elif level == "CRITICAL":
        log.setLevel(logging.CRITICAL)
    else:
        log.warning("invalid log level: %s, will set to DEBUG as default..." % (level))
