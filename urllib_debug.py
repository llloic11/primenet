#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division, print_function
try:
    # Python3
    from urllib.request import HTTPHandler, HTTPSHandler
    from urllib.response import addinfourl
except ImportError:
    # Python2
    from urllib2 import HTTPHandler, HTTPSHandler
    from urllib2 import addinfourl

from io import BytesIO

#######################################################################################################
# Debug tools
#######################################################################################################
# Spy Handlers for HTTP and HTTPS request
# They store the request in request_%d.log in current directory and responses in response_%d.log
_req_count = 0
def spy_http_open(req, super_method):
	# super_method arg is http_open or https_open to be called
	global _req_count
	request_file = "request_{0}.log".format(_req_count)
	response_file = "response_{0}.log".format(_req_count)
	try:
		with open(request_file, "w") as output:
			_req_count += 1
			print("{0} {1}".format(req.get_method(), req.get_full_url()), file=output)
			for k,v in req.header_items():
				if k not in "User-agent:": # depends in the python version, so it is not suitable for 
					print("{0}: {1}".format(k,v), file=output)
			print('', file=output)
			if req.data is not None:
				print(req.data.decode('utf-8','replace'), file=output)
			print('', file=output)
		# TODO: intercept exceptions that can be raise by http_open() and r.read() to log them ?
		r = super_method(req)
		with open(response_file, "wt") as output:
			# get header and data
			print('HTTP/1.1 {0} {1}'.format(r.code, r.msg), file=output)
			headers = r.info()
			print(headers, file=output)
			data = r.read()
			print(data.decode('utf-8', 'replace'), file=output)
			# And return a fake response
			resp = addinfourl(BytesIO(data), headers, req.get_full_url())
			resp.code = r.code
			resp.msg = r.msg
			return resp
	except (IOError,OSError):
		pass
	return r

# The double inheritance with object is necessary in Python2
# to make the class a new style class and have super() works
# see https://stackoverflow.com/a/18392639/3446843
class SpyHTTPHandler(HTTPHandler, object):
	#def __init__(self):
	#	self._debuglevel = 2
	def http_open(self, req):
		return spy_http_open(req, super(SpyHTTPHandler, self).http_open)

class SpyHTTPSHandler(HTTPSHandler, object):
	def https_open(self, req):
		return spy_http_open(req, super(SpyHTTPSHandler, self).https_open)

