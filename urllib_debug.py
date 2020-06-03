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

def save_request(req, output):
	print("{0} {1}".format(req.get_method(), req.get_full_url()), file=output)
	for k,v in sorted(req.header_items()):
		if k not in "User-agent:": # depends in the python version, so it is not suitable for reference
			print("{0}: {1}".format(k,v), file=output)
	print('', file=output) # For parsing, the first empty line is the limit between headers and data
	if req.data is not None:
		print(req.data.decode('utf-8','replace'), file=output)

#######################################################################################################
# Debug tools
#######################################################################################################
# Spy Handlers for HTTP and HTTPS request
# They store the request in request_%d.log in current directory and responses in response_%d.log
_req_count = 0
def spy_http_open(req, super_method):
	# super_method arg is http_open or https_open to be called
	global _req_count
	request_filename = "request_{0}.log".format(_req_count)
	response_filename = "response_{0}.log".format(_req_count)
	try:
		with open(request_filename, "wt") as output:
			_req_count += 1
			save_request(req, output)
		# TODO: intercept exceptions that can be raise by http_open() and r.read() to log them ?
		r = super_method(req)
		with open(response_filename, "wt") as output:
			# get header and data
			print('HTTP/1.1 {0} {1}'.format(r.code, r.msg), file=output)
			headers = '\n'.join( "{0}: {1}".format(k,v) for k,v in sorted(r.getheaders()) )
			print(headers, '\n', file=output)
			data = r.read()
			print(data.decode('utf-8', 'replace'), file=output)
			# And return a fake response
			resp = addinfourl(BytesIO(data), r.info(), req.get_full_url())
			resp.code = r.code
			resp.msg = r.msg
			return resp
	except (IOError,OSError):
		pass
	return r

# The double inheritance with object is necessary in Python2 (not in Python3 but it doesn't hurt)
# to make the class a new style class and have super() works.
# See https://stackoverflow.com/a/18392639/3446843
class SpyHTTPHandler(HTTPHandler, object):
	#def __init__(self):
	#	self._debuglevel = 2
	def http_open(self, req):
		return spy_http_open(req, super(SpyHTTPHandler, self).http_open)

class SpyHTTPSHandler(HTTPSHandler, object):
	def https_open(self, req):
		return spy_http_open(req, super(SpyHTTPSHandler, self).https_open)

#######################################################################################################
# Tests tools
#######################################################################################################
# The idea is to store the request in request_%d.log and send the result from response_%d.log as a response
import sys
if sys.version_info[0] == 2:
	# py2
	import mimetools
	from StringIO import StringIO
else:
	# py3
	import email

def test_http_open(req, super_method):
	# super_method arg is http_open or https_open to be called
	global _req_count
	request_filename = "request_{0}.log".format(_req_count)
	response_filename = "response_{0}.log".format(_req_count)
	try:
		# save the request
		with open(request_filename, "wt") as output:
			_req_count += 1
			save_request(req, output)
	except (IOError,OSError):
		pass
	# TODO compare with expected value ?
	# Built the response for the response file
	with open(response_filename, "r") as response_file:
		# get code and msg
		http_version, code, msg = response_file.readline().rstrip().split(" ", 2)
		code = int(code)
		# read headers
		headers = []
		while True:
			line = response_file.readline().rstrip()
			if line == '': break
			headers.append(line)
		if sys.version_info[0] == 2:
			# py2
			headers = mimetools.Message(StringIO('\n'.join(headers)))
		else:
			# py3
			headers = email.message_from_string('\n'.join(headers))
		# read data
		data = response_file.read().encode('utf-8')
		# And return a fake response
		resp = addinfourl(BytesIO(data), headers, req.get_full_url(), code=code)
		resp.msg = msg
		return resp

class TestHTTPHandler(HTTPHandler, object):
	def http_open(self, req):
		return test_http_open(req, super(TestHTTPHandler, self).http_open)

class TestHTTPSHandler(HTTPSHandler, object):
	def https_open(self, req):
		return test_http_open(req, super(TestHTTPSHandler, self).https_open)

# vim: noexpandtab ts=4 sts=0 sw=0
