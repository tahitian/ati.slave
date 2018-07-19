import pycurl
import StringIO
import sys

def curl_get(url, options = None):
    buf = StringIO.StringIO()
    curl = pycurl.Curl()
    curl.setopt(pycurl.CONNECTTIMEOUT, 5)
    curl.setopt(pycurl.TIMEOUT, 5)
    curl.setopt(pycurl.WRITEFUNCTION, buf.write)
    curl.setopt(pycurl.FOLLOWLOCATION, 1)
    curl.setopt(pycurl.SSL_VERIFYPEER, 0)
    curl.setopt(pycurl.SSL_VERIFYHOST, 0)
    if options:
        for option in options:
            curl.setopt(option, options[option])
    curl.setopt(pycurl.URL, url)
    code = 0
    try:
        curl.perform()
        code = curl.getinfo(pycurl.HTTP_CODE)
    except Exception, e:
        sys.stderr.write("%r\n" % e)
    curl.close()
    return code, buf.getvalue()
