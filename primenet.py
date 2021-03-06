#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Automatic assignment handler for Mlucas.
# This handles LL and PRP testing (first-time and double-check), i.e. all the worktypes supported by the program.
# EWM: adapted from https://github.com/MarkRose/primetools/blob/master/mfloop.py by teknohog and Mark Rose, with help rom Gord Palameta.
# 2020: support for computer registration and assignment-progress via direct Primenet-v5-API calls by Loïc Le Loarer <loic@le-loarer.org>.

# This script is intended to be run alongside Mlucas - use it to register your computer (if you've not previously done so)
# and then reinvoke in periodic-update mode to automatically fetch work from the Primenet server, report latest results and
# report the status of currently-in-progress assignments to the server, which you can view in a convenient dashboard form via
# login to the server and clicking Account/Team Info --> My Account --> CPUs. (Or directly via URL: https://www.mersenne.org/cpus/)

################################################################################
#                                                                              #
#   (C) 2017-2020 by Ernst W. Mayer.                                                #
#                                                                              #
#  This program is free software; you can redistribute it and/or modify it     #
#  under the terms of the GNU General Public License as published by the       #
#  Free Software Foundation; either version 2 of the License, or (at your      #
#  option) any later version.                                                  #
#                                                                              #
#  This program is distributed in the hope that it will be useful, but WITHOUT #
#  ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or       #
#  FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for   #
#  more details.                                                               #
#                                                                              #
#  You should have received a copy of the GNU General Public License along     #
#  with this program; see the file GPL.txt.  If not, you may view one at       #
#  http://www.fsf.org/licenses/licenses.html, or obtain one by writing to the  #
#  Free Software Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA     #
#  02111-1307, USA.                                                            #
#                                                                              #
################################################################################

from __future__ import division, print_function
import sys
import os.path
import re
from time import sleep
from optparse import OptionParser, OptionGroup
from hashlib import sha256
import json
import platform

# More python3-backward-incompatibility-breakage-related foo - thanks to Gord Palameta for the workaround:
try:
    # Python3
    import http.cookiejar as cookiejar
    from urllib.error import URLError, HTTPError
    from urllib.parse import urlencode
    from urllib.request import build_opener, install_opener, urlopen
    from urllib.request import HTTPCookieProcessor
except ImportError:
    # Python2
    import cookielib as cookiejar
    from urllib2 import URLError, HTTPError
    from urllib import urlencode
    from urllib2 import build_opener, install_opener, urlopen
    from urllib2 import HTTPCookieProcessor

try:
    from configparser import ConfigParser, Error as ConfigParserError
except ImportError:
    from ConfigParser import ConfigParser, Error as ConfigParserError  # ver. < 3.0

from collections import namedtuple

if sys.version_info[:2] >= (3,7):
	# If is OK to use dict in 3.7+ because insertion order is garantied to be preserved
	# Since it is also faster, it is better to use raw dict()
	OrderedDict = dict
else:
	try:
		from collections import OrderedDict
	except ImportError:
		# For python2.6 and before which don't have OrderedDict
		try:
			from ordereddict import OrderedDict
		except ImportError:
			# Tests will not work correctly but it doesn't affect the functionnality
			OrderedDict = dict

primenet_v5_burl = "http://v5.mersenne.org/v5server/?"
primenet_v5_bargs = OrderedDict((("px", "GIMPS"), ("v", 0.95)))
primenet_baseurl = "https://www.mersenne.org/"
primenet_login = False

class primenet_api:
	ERROR_OK = 0
	ERROR_SERVER_BUSY = 3
	ERROR_INVALID_VERSION = 4
	ERROR_INVALID_TRANSACTION = 5
	ERROR_INVALID_PARAMETER = 7 #   Returned for length, type, or character invalidations.
	ERROR_ACCESS_DENIED = 9
	ERROR_DATABASE_FULL_OR_BROKEN = 13
	# Account related errors:
	ERROR_INVALID_USER = 21
	# Computer cpu/software info related errors:
	ERROR_OBSOLETE_CLIENT = 31
	ERROR_UNREGISTERED_CPU = 30
	ERROR_STALE_CPU_INFO = 32
	ERROR_CPU_IDENTITY_MISMATCH = 33
	ERROR_CPU_CONFIGURATION_MISMATCH = 34
	# Work assignment related errors:
	ERROR_NO_ASSIGNMENT = 40
	ERROR_INVALID_ASSIGNMENT_KEY = 43
	ERROR_INVALID_ASSIGNMENT_TYPE = 44
	ERROR_INVALID_RESULT_TYPE = 45
	ERROR_INVALID_WORK_TYPE = 46
	ERROR_WORK_NO_LONGER_NEEDED = 47
	PRIMENET_AR_NO_RESULT		= 0		# No result, just sending done msg
	PRIMENET_AR_TF_FACTOR		= 1		# Trial factoring, factor found
	PRIMENET_AR_P1_FACTOR		= 2		# P-1, factor found
	PRIMENET_AR_ECM_FACTOR		= 3		# ECM, factor found
	PRIMENET_AR_TF_NOFACTOR		= 4		# Trial Factoring no factor found
	PRIMENET_AR_P1_NOFACTOR		= 5		# P-1 Factoring no factor found
	PRIMENET_AR_ECM_NOFACTOR	= 6		# ECM Factoring no factor found
	PRIMENET_AR_LL_RESULT		= 100	# LL result, not prime
	PRIMENET_AR_LL_PRIME		= 101	# LL result, Mersenne prime
	PRIMENET_AR_PRP_RESULT		= 150	# PRP result, not prime
	PRIMENET_AR_PRP_PRIME		= 151	# PRP result, probably prime

def debug_print(text, file=sys.stdout):
	if options.debug or file == sys.stderr:
		caller_name = sys._getframe(1).f_code.co_name
		if caller_name == '<module>':
			caller_name = 'main loop'
		caller_string = caller_name + ": "
		print(progname + ": " + caller_string + str(text), file=file)
		file.flush()

def greplike(pattern, l):
	output = []
	for line in l:
		s = pattern.search(line)
		if s:
			output.append(s.group(0))
	return output

def num_to_fetch(l, targetsize):
	num_existing = len(l)
	num_needed = targetsize - num_existing
	return max(num_needed, 0)

def readonly_list_file(filename, mode="r"):
	# Used when there is no intention to write the file back, so don't
	# check or write lockfiles. Also returns a single string, no list.
	try:
		with open(filename, mode=mode) as File:
			contents = File.readlines()
			File.close()
			return [ x.rstrip() for x in contents ]
	except (IOError,OSError):
		return []

def read_list_file(filename, mode="r"):
	return readonly_list_file(filename, mode=mode)

def write_list_file(filename, l, mode="w"):
	# A "null append" is meaningful, as we can call this to clear the
	# lockfile. In this case the main file need not be touched.
	if not ( "a" in mode and len(l) == 0):
		newline = b'\n' if 'b' in mode else '\n'
		content = newline.join(l) + newline
		File = open(filename, mode)
		File.write(content)
		File.close()

def primenet_fetch(num_to_get):
	if not primenet_login:
		return []
	# As of early 2018, here is the full list of assignment-type codes supported by the Primenet server; Mlucas
	# v18 (and thus this script) supports only the subset of these indicated by an asterisk in the left column.
	# Supported assignment types may be specified via either their PrimeNet number code or the listed Mnemonic:
	#			Worktype:
	# Code		Mnemonic			Description
	# ----	-----------------	-----------------------
	#    0						Whatever makes the most sense
	#    1						Trial factoring to low limits
	#    2						Trial factoring
	#    4						P-1 factoring
	#    5						ECM for first factor on Mersenne numbers
	#    6						ECM on Fermat numbers
	#    8						ECM on mersenne cofactors
	# *100	SmallestAvail		Smallest available first-time tests
	# *101	DoubleCheck			Double-checking
	# *102	WorldRecord			World record primality tests
	# *104	100Mdigit			100M digit number to LL test (not recommended)
	# *150	SmallestAvailPRP	First time PRP tests (Gerbicz)
	# *151	DoubleCheckPRP		Doublecheck PRP tests (Gerbicz)
	# *152	WorldRecordPRP		World record sized numbers to PRP test (Gerbicz)
	# *153	100MdigitPRP		100M digit number to PRP test (Gerbicz)
	#  160						PRP on Mersenne cofactors
	#  161						PRP double-checks on Mersenne cofactors

	# Convert mnemonic-form worktypes to corresponding numeric value, check worktype value vs supported ones:
	if options.worktype == "SmallestAvail":
		options.worktype = "100"
	elif options.worktype == "DoubleCheck":
		options.worktype = "101"
	elif options.worktype == "WorldRecord":
		options.worktype = "102"
	elif options.worktype == "100Mdigit":
		options.worktype = "104"
	if options.worktype == "SmallestAvailPRP":
		options.worktype = "150"
	elif options.worktype == "DoubleCheckPRP":
		options.worktype = "151"
	elif options.worktype == "WorldRecordPRP":
		options.worktype = "152"
	elif options.worktype == "100MdigitPRP":
		options.worktype = "153"
	supported = set(['100','101','102','104','150','151','152','153'])
	if not options.worktype in supported:
		debug_print("Unsupported/unrecognized worktype = " + options.worktype)
		return []
	assignment = OrderedDict((
		("cores","1"),
		("num_to_get", num_to_get),
		("pref", options.worktype),
		("exp_lo", ""),
		("exp_hi", ""),
		("B1", "Get Assignments")
	))
	try:
		openurl = primenet_baseurl + "manual_assignment/?" + urlencode(assignment)
		debug_print("Fetching work via URL = "+openurl)
		r = primenet.open(openurl)
		return greplike(workpattern, [ line.decode('utf-8','replace') for line in r.readlines() ] )
	except URLError:
		debug_print("URL open error at primenet_fetch")
		return []

def get_assignment(progress):
	w = read_list_file(workfile)
	tasks = greplike(workpattern, w)
	(percent, time_left) = None, None
	if progress is not None and type(progress) == tuple and len(progress) == 2:
		(percent, time_left) = progress # unpack update_progress output
	num_cache = int(options.num_cache)
	if percent is not None and percent >= int(options.percent_limit):
		num_cache += 1
		debug_print("Progress of current assignment is {0:.2f} and bigger than limit ({1}), so num_cache is increased by one to {2}".format(percent, options.percent_limit, num_cache))
	elif time_left is not None and time_left <= max(3*options.timeout, 24*3600):
		# use else if here is important,
		# time_left and percent increase are exclusive (don't want to do += 2)
		num_cache += 1
		debug_print("Time_left is {0} and smaller than limit ({1}), so num_cache is increased by one to {2}".format(time_left, max(3*options.timeout, 24*3600), num_cache))
	num_to_get = num_to_fetch(tasks, num_cache)

	if num_to_get < 1:
		debug_print(workfile + " already has " + str(len(tasks)) + " >= " + str(num_cache) + " entries, not getting new work")
		return 0

	debug_print("Fetching " + str(num_to_get) + " assignments")
	new_tasks = primenet_fetch(num_to_get)
	num_fetched = len(new_tasks)
	if num_fetched > 0:
		debug_print("Fetched {0} assignments:".format(num_fetched))
		for new_task in new_tasks:
			debug_print("{0}".format(new_task))
	write_list_file(workfile, new_tasks, "a")
	if num_fetched < num_to_get:
		debug_print("Error: Failed to obtain requested number of new assignments, " + str(num_to_get) + " requested, " + str(num_fetched) + " successfully retrieved")
	return num_fetched

def mersenne_find(line, complete=True):
	# Pre-v19 old-style HRF-formatted result used "Program:..."; starting w/v19 JSON-formatted result uses "program",
	return re.search("[Pp]rogram", line)

try:
    from statistics import median_low
except ImportError:
    def median_low(mylist):
        sorts = sorted(mylist)
        length = len(sorts)
        return sorts[(length-1)//2]

def parse_stat_file(p):
	statfile = 'p' + str(p) + '.stat'
	w = readonly_list_file(statfile) # appended line by line, no lock needed
	found = 0
	regex = re.compile("Iter# = (.+?) .*?(\d+\.\d+) (m?sec)/iter")
	list_usec_per_iter = []
	# get the 5 most recent Iter line
	for line in reversed(w):
		res = regex.search(line)
		if res:
			found += 1
			# keep the last iteration to compute the percent of progress
			if found == 1:
				iteration = int(res.group(1))
			usec_per_iter = float(res.group(2))
			unit = res.group(3)
			if unit == "sec":
				usec_per_iter *= 1000
			list_usec_per_iter.append(usec_per_iter)
			if found == 5: break
	if found == 0: return 0, None # iteration is 0, but don't know the estimated speed yet
	# take the media of the last grepped lines
	usec_per_iter = median_low(list_usec_per_iter)
	return iteration, usec_per_iter

def parse_v5_resp(r):
	ans = dict()
	for line in r.splitlines():
		if line == "==END==": break
		option,_,value = line.partition("=")
		ans[option]=value
	return ans

def send_request(guid, args):
	args["g"] = guid
	# to mimic mprime, it is necessary to add safe='"{}:,' argument to urlencode, in
	# particular to encode JSON in result submission. But safe is not supported by python2...
	url_args = urlencode(args)
	# Only really usefull for t = "uc", not for "ap", is it for "ar" ?
	url_args += "&ss=19191919&sh=ABCDABCDABCDABCDABCDABCDABCDABCD"
	try:
		# don't need to use primenet opener because this API doesn't have cookies
		r = urlopen(primenet_v5_burl+url_args)
	except HTTPError as e:
		debug_print("ERROR receiving answer to request: "+str(primenet_v5_burl+url_args), file=sys.stderr)
		debug_print(e, file=sys.stderr)
		return None
	except URLError as e:
		debug_print("ERROR connecting to server for request: "+str(primenet_v5_burl+url_args), file=sys.stderr)
		debug_print(e, file=sys.stderr)
		return None
	return parse_v5_resp(r.read().decode("utf-8","replace"))

from random import getrandbits
def create_new_guid():
	guid = hex(getrandbits(128))
	if guid[:2] == '0x': guid = guid[2:] # remove the 0x prefix
	if guid[-1] == 'L': guid = guid[:-1] # remove trailling 'L' in python2
	# add missing 0 to the beginning"
	guid = (32-len(guid))*"0" + guid
	return guid

def register_instance(guid):
	# register the instance to server, guid is the instance identifier
	if options.username is None or options.hostname is None:
		parser.error("To register the instance, --username and --hostname are required")
	hardware_id = sha256(options.cpu_model.encode("utf-8")).hexdigest()[:32] # similar as mprime
	args = primenet_v5_bargs.copy()
	args["t"] = "uc"					# update compute command
	args["a"] = "Linux64,Mlucas,v19"	#
	if config.has_option("primenet", "sw_version"):
			args["a"] = config.get("primenet", "sw_version")
	args["wg"] = ""						# only filled on Windows by mprime
	args["hd"] = hardware_id			# 32 hex char (128 bits)
	args["c"] = options.cpu_model[:64]	# CPU model (len between 8 and 64)
	args["f"] = options.features[:64]	# CPU option (like asimd, max len 64)
	args["L1"] = options.L1				# L1 cache size in KBytes
	args["L2"] = options.L2				# L2 cache size in KBytes
										# if smaller or equal to 256,
										# server refuses to gives LL assignment
	args["np"] = options.np				# number of cores
	args["hp"] = options.hp				# number of hyperthreading cores
	args["m"] = options.memory			# number of megabytes of physical memory
	args["s"] = options.frequency		# CPU frequency
	args["h"] = 24						# pretend to run 24h/day
	args["r"] = 1000					# pretend to run at 100%
	args["u"] = options.username		#
	args["cn"] = options.hostname[:20]	# truncate to 20 char max
	if guid is None:
		guid = create_new_guid()
	result = send_request(guid, args)
	if result is None:
		parser.error("Error while registering on mersenne.org")
	elif int(result["pnErrorResult"]) != 0:
		parser.error("Error while registering on mersenne.org\nReason: "+result["pnErrorDetail"])
	config_write(config, guid=guid)
	print("GUID {guid} correctly registered with the following features:".format(guid=guid))
	print("Username: {0}".format(options.username))
	print("Hostname: {0}".format(options.hostname))
	print("CPU model: {0}".format(options.cpu_model))
	print("CPU features: {0}".format(options.features))
	print("CPU L1 cache size: {0}kB".format(options.L1))
	print("CPU L2 cache size: {0}kB".format(options.L2))
	print("CPU cores: {0}".format(options.np))
	print("CPU thread per core: {0}".format(options.hp))
	print("CPU frequency: {0}MHz".format(options.frequency))
	print("Memory size: {0}MB".format(options.memory))
	print("If you want to change the value, please rerun with the corresponding options or edit the local.ini file and rerun with --register option")
	print("You can see the result in this page:")
	print("https://www.mersenne.org/editcpu/?g={guid}".format(guid=guid))
	return

def config_read():
	config = ConfigParser(dict_type=OrderedDict)
	try:
		config.read([localfile])
	except ConfigParserError as e:
		debug_print("ERROR reading {0} file:".format(localfile), file=sys.stderr)
		debug_print(e, file=sys.stderr)
	if not config.has_section("primenet"):
		# Create the section to avoid having to test for it later
		config.add_section("primenet")
	return config

def get_guid(config):
	try:
		return config.get("primenet", "guid")
	except ConfigParserError:
		return None

def config_write(config, guid=None):
	# generate a new local.ini file
	if guid is not None: # update the guid if necessary
		config.set("primenet", "guid", guid)
	with open(localfile, "w") as configfile:
		config.write(configfile)

def merge_config_and_options(config, options):
	# getattr and setattr allow access to the options.xxxx values by name
	# which allow to copy all of them programmatically instead of having
	# one line per attribute. Only the attr_to_copy list need to be updated
	# when adding an option you want to copy from argument options to local.ini config.
	attr_to_copy = ["username", "password", "worktype", "num_cache", "percent_limit",
		"hostname", "cpu_model", "features", "frequency", "memory", "L1", "L2", "np", "hp"]
	updated = False
	for attr in attr_to_copy:
		# if "attr" has its default value in options, copy it from config
		attr_val = getattr(options, attr)
		if attr_val == parser.defaults[attr] \
		   and config.has_option("primenet", attr):
			# If no option is given and the option exists in local.ini, take it from local.ini
			new_val = config.get("primenet", attr)
			# config file values are always str()
			# they need to be converted to the expected type from options
			if attr_val is not None:
				new_val = type(attr_val)(new_val)
			setattr(options, attr, new_val)
		elif attr_val is not None and (not config.has_option("primenet", attr) \
		   or config.get("primenet", attr) != str(attr_val)):
			# If an option is given (even default value) and it is not already
			# identical in local.ini, update local.ini
			debug_print("update local.ini with {0}={1}".format(attr, attr_val))
			config.set("primenet", attr, str(attr_val))
			updated = True
	return updated

Assignment = namedtuple('Assignment', "id p is_prp iteration usec_per_iter")
def update_progress():
	w = readonly_list_file(workfile)
	tasks = greplike(workpattern, w)
	if not len(tasks): return # don't update if no worktodo
	config_updated = False
	# Treat the first assignment. Only this one is used to save the usec_per_iter
	# The idea is that the first assignment is having a .stat file with correct values
	# Most of the time, a later assignment would not have a .stat file to obtain information,
	# but if it has, it may come from an other computer if the user moved the files, and so
	# it doesn't have revelant values for speed estimation.
	# Using usec_per_iter from one p to another is a good estimation if both p are close enougth
	# if there is big gap, it will be other or under estimated.
	# Any idea for a better estimation of assignment duration when only p and type (LL or PRP) is known ?
	assignment = get_progress_assignment(tasks[0])
	usec_per_iter = assignment.usec_per_iter
	if usec_per_iter is not None:
		config.set("primenet", "usec_per_iter", "{0:.2f}".format(usec_per_iter))
		config_updated = True
	elif config.has_option("primenet", "usec_per_iter"):
		# If not speed available, get it from the local.ini file
		usec_per_iter = float(config.get("primenet", "usec_per_iter"))
	percent, time_left = compute_progress(assignment.p, assignment.iteration, usec_per_iter)
	debug_print("p:{0} is {1:.2f}% done".format(assignment.p, percent))
	if time_left is None:
		debug_print("Finish cannot be estimated")
	else:
		debug_print("Finish estimated in {0:.1f} days (used {1:.1f} msec/iter estimation)".format(time_left/3600/24, usec_per_iter))
	send_progress(assignment.id, assignment.is_prp, percent, time_left)
	# Do the other assignment accumulating the time_lefts
	cur_time_left = time_left
	for task in tasks[1:]:
		assignment = get_progress_assignment(task)
		percent, time_left = compute_progress(assignment.p, assignment.iteration, usec_per_iter)
		debug_print("p:{0} is {1:.2f}% done".format(assignment.p, percent))
		if time_left is None:
			debug_print("Finish cannot be estimated")
		else:
			cur_time_left += time_left
			debug_print("Finish estimated in {0:.1f} days (used {1:.1f} msec/iter estimation)".format(cur_time_left/3600/24, usec_per_iter))
		send_progress(assignment.id, assignment.is_prp, percent, cur_time_left)
	config_write(config)
	return percent, cur_time_left

def get_progress_assignment(task):
	found = workpattern.search(task)
	if not found:
		# TODO: test this error
		debug_print("ERROR: Unable to extract valid Primenet assignment ID from entry in " + workfile + ": " + str(task), file=sys.stderr)
		return
	assignment_id = found.group(2)
	is_prp = found.group(1) == "PRP"
	debug_print("type = {0}, assignment_id = {1}".format(found.group(1), assignment_id))
	found = task.split(",")
	idx = 3 if is_prp else 1
	if len(found) <= idx:
		debug_print("Unable to extract valid exponent substring from entry in " + workfile + ": " + str(task))
		return None, None
	# Extract the subfield containing the exponent, whose position depends on the assignment type:
	p = int(found[idx])
	iteration, usec_per_iter = parse_stat_file(p)
	return Assignment(assignment_id, p, is_prp, iteration, usec_per_iter)

def compute_progress(p, iteration, usec_per_iter):
	percent = 100*float(iteration)/float(p)
	if usec_per_iter is None:
		return percent, None
	iteration_left = p - iteration
	time_left = int(usec_per_iter * iteration_left / 1000)
	return percent, time_left

def send_progress(assignment_id, is_prp, percent, time_left, retry_count=0):
	guid = get_guid(config)
	if guid is None:
		debug_print("Cannot update, the registration is not done", file=sys.stderr)
		debug_print("Call primenet.py with --register option", file=sys.stderr)
		return
	if retry_count > 5: return
	# Assignment Progress fields:
	# g= the machine's GUID (32 chars, assigned by Primenet on 1st-contact from a given machine, stored in 'guid=' entry of local.ini file of rundir)
	#
	args=primenet_v5_bargs.copy()
	args["t"] = "ap" # update compute command
	# k= the assignment ID (32 chars, follows '=' in Primenet-geerated workfile entries)
	args["k"] = assignment_id
	# p= progress in %-done, 4-char format = xy.z
	args["p"] = "{0:.1f}".format(percent)
	# d= when the client is expected to check in again (in seconds ... )
	args["d"] = options.timeout if options.timeout else 24*3600
	# e= the ETA of completion in seconds, if unknown, just put 1 week
	args["e"] = time_left if time_left is not None else 7*24*3600
	# c= the worker thread of the machine ... always sets = 0 for now, elaborate later if desired
	args["c"] = 0
	# stage= LL in this case, although an LL test may be doing TF or P-1 work first so it's possible to be something besides LL
	if not is_prp:
		args["stage"] = "LL"
	retry = False
	result = send_request(guid, args)
	if result is None:
		debug_print("ERROR while updating on mersenne.org", file=sys.stderr)
		# Try again
		retry = True
	else:
		rc = int(result["pnErrorResult"])
		if rc == primenet_api.ERROR_OK:
			debug_print("Update correctly send to server")
		elif rc == primenet_api.ERROR_STALE_CPU_INFO:
			debug_print("STALE CPU INFO ERROR: re-send computer update")
			# rerun --register
			register_instance(guid)
			retry = True
		elif rc == primenet_api.ERROR_UNREGISTERED_CPU:
			debug_print("UNREGISTERED CPU ERROR: pick a new GUID and register again")
			# corrupted GUI: change GUID, and rerun --register
			register_instance(None)
			retry = True
		elif rc == primenet_api.ERROR_SERVER_BUSY:
			retry = True
		else:
			# TODO: treat more errors correctly in all send_request callers
			# primenet_api.ERROR_INVALID_ASSIGNMENT_KEY
			# primenet_api.ERROR_WORK_NO_LONGER_NEEDED
			# drop the assignment
			debug_print("ERROR while updating on mersenne.org", file=sys.stderr)
			debug_print("Code: "+str(rc), file=sys.stderr)
			debug_print("Reason: "+result["pnErrorDetail"], file=sys.stderr)
	if retry:
		return send_progress(assignment_id, is_prp, percent, time_left, retry_count+1)
	return

def submit_one_line(sendline):
	"""Submit one line"""
	try:
		ar = json.loads(sendline)
		is_json = True
	except json.decoder.JSONDecodeError:
		is_json = False
	guid = get_guid(config)
	if guid is not None and is_json:
		# If registered and the line is a JSON, submit using the v API
		# The result will be attributed to the registered computer
		sent = submit_one_line_v5(sendline, guid, ar)
	else:
		# The result will be attributed to "Manual testing"
		sent = submit_one_line_manually(sendline)
	return sent

def get_result_type(ar):
	"""Extract result type from JSON result"""
	if ar['worktype'] == 'LL':
		if ar['status'] == 'P':
			return primenet_api.PRIMENET_AR_LL_PRIME
		else:
			return primenet_api.PRIMENET_AR_LL_RESULT
	elif ar['worktype'].startswith('PRP'):
		if ar['status'] == 'P':
			return primenet_api.PRIMENET_AR_PRP_PRIME
		else:
			return primenet_api.PRIMENET_AR_PRP_RESULT
	else:
		raise ValueError("This is a bug in primenet.py, Unsupported worktype {0}".format(ar['worktype']))

def submit_one_line_v5(sendline, guid, ar):
	"""Submit one result line using V5 API, will be attributed to the computed identified by guid"""
	"""Return False if the submission should be retried"""
	# JSON is required because assignment_id is necessary in that case
	# and it is not present in old output format.
	debug_print("Submitting using V5 API\n" + sendline)
	aid = ar['aid']
	result_type = get_result_type(ar)
	args = primenet_v5_bargs.copy()
	args["t"] = "ar"								# assignment result
	args["k"] = ar['aid'] if 'aid' in ar else 0		# assignment id
	args["m"] = sendline							# message is the complete JSON string
	args["r"] = result_type							# result type
	args["d"] = 1									# done: 0 for no closing is used for partial results
	args["n"] = ar['exponent']
	if result_type in (primenet_api.PRIMENET_AR_LL_RESULT, primenet_api.PRIMENET_AR_LL_PRIME):
		if result_type == primenet_api.PRIMENET_AR_LL_RESULT:
			args["rd"] = ar['res64']
		if 'shift-count' in ar:
			args['sc'] = ar['shift-count']
		if 'error-code' in ar:
			args["ec"] = ar['error-code']
	elif result_type in (primenet_api.PRIMENET_AR_PRP_RESULT, primenet_api.PRIMENET_AR_PRP_PRIME):
		args.update((("A", 1), ("b", 2), ("c", -1)))
		if result_type == primenet_api.PRIMENET_AR_PRP_RESULT:
			args["rd"] = ar['res64']
		if 'error-code' in ar:
			args["ec"] = ar['error-code']
		if 'known-factors' in ar:
			args['nkf'] = len(ar['known-factors'])
		args["base"] = ar['worktype'][4:]	# worktype == PRP-base
		if 'residue-type' in ar:
			args["rt"] = ar['residue-type']
		if 'shift-count' in ar:
			args['sc'] = ar['shift-count']
		if 'errors' in ar:
			args['gbz'] = 1
	args['fftlen'] = ar['fft-length']
	result = send_request(guid, args)
	if result is None:
		debug_print("ERROR while submitting result on mersenne.org: assignment_id={0}".format(aid), file=sys.stderr)
		# if this happens, the submission can be retried
		# since no answer has been received from the server
		return False
	elif int(result["pnErrorResult"]) == primenet_api.ERROR_OK:
		debug_print("Result correctly send to server: assignment_id={0}".format(aid))
		if result["pnErrorDetail"] != "SUCCESS":
			debug_print("server message: "+result["pnErrorDetail"])
	else: # non zero ERROR code
		debug_print("ERROR while submitting result on mersenne.org: assignment_id={0}".format(aid), file=sys.stderr)
		if int(result["pnErrorResult"]) is primenet_api.ERROR_UNREGISTERED_CPU:
			# should register again and retry
			debug_print("ERROR UNREGISTERED CPU: Please remove guid line from local.ini, run with --register and retry", file=sys.stderr)
			return False
		elif int(result["pnErrorResult"]) is primenet_api.ERROR_INVALID_PARAMETER:
			debug_print("INVALID PARAMETER: this is a bug in primenet.py, please notify the author", file=sys.stderr)
			debug_print("Reason: "+result["pnErrorDetail"], file=sys.stderr)
			return False
		else:
			# In all other error case, the submission must not be retried
			debug_print("Reason: "+result["pnErrorDetail"], file=sys.stderr)
			return True
	return True

def submit_one_line_manually(sendline):
	"""Submit results using manual testing, will be attributed to "Manual Testing" in mersenne.org"""
	debug_print("Submitting using manual results\n" + sendline)
	try:
		post_data = urlencode({"data": sendline}).encode('utf-8')
		r = primenet.open(primenet_baseurl + "manual_result/default.php", post_data)
		res = r.read()
		if b"Error" in res:
			res_str = res.decode("utf-8", "replace")
			ibeg = res_str.find("Error")
			iend = res_str.find("</div>", ibeg)
			print("Submission failed: '{0}'".format(res_str[ibeg:iend]))
		elif b"Accepted" in res:
			pass
		else:
			print("submit_work: Submission of results line '" + sendline + "' failed for reasons unknown - please try manual resubmission.")
	except URLError:
		debug_print("URL open ERROR")
	return True	# EWM: Append entire results_send rather than just sent to avoid resubmitting
				# bad results (e.g. previously-submitted duplicates) every time the script executes.

def submit_work():
	results_send = read_list_file(sentfile)
	# Only submit completed work, i.e. the exponent must not exist in worktodo file any more
	results = readonly_list_file(resultsfile) # appended line by line, no lock needed
	# EWM: Note that read_list_file does not need the file(s) to exist - nonexistent files simply yield 0-length rs-array entries.
	results = filter(mersenne_find, results)	# remove nonsubmittable lines from list of possibles

	results_send = [line for line in results if line not in results_send]	# if a line was previously submitted, discard

	# Only for new results, to be appended to results_sent
	sent = []

	if len(results_send) == 0:
		debug_print("No complete results found to send.")
		return
	# EWM: Switch to one-result-line-at-a-time submission to support error-message-on-submit handling:
	for sendline in results_send:
		is_sent = submit_one_line(sendline)
		if is_sent:
			sent.append(sendline)
	write_list_file(sentfile, sent, "a")

#######################################################################################################
#
# Start main program here
#
#######################################################################################################

parser = OptionParser(version="primenet.py 19.1", description=\
"""This program is used to fill worktodo.ini with assignments and send the results for Mlucas
program. It also saves its configuration to local.ini file, so it is necessary to gives the arguments only the first time you call it. Arguments are recovered for local.ini if not given.
If --register is given, it registers the current Mlucas instance to mersenne.org (see all the options identify your CPU correctly). Registering is optionnal, but if registered, the progress can be sent and your CPU monitored on your account on the website.
Then, without --register, it fetches assignment and send results to mersenne.org using manual assignment process on a "timeout" basic, or only once if timeout=0.
"""
)

# options not saved to local.ini
parser.add_option("-d", "--debug", action="count", dest="debug", default=False, help="Display debugging info")
parser.add_option("-w", "--workdir", dest="workdir", default=".", help="Working directory with worktodo.ini and results.txt from mlucas, and local.ini created by this program. Default current directory")

# all other options are saved to local.ini (except --register)
parser.add_option("-u", "--username", dest="username", help="Primenet user name")
parser.add_option("-p", "--password", dest="password", help="Primenet password")

# -t is reserved for timeout, instead use -T for assignment-type preference:
parser.add_option("-T", "--worktype", dest="worktype", default="101", help="Worktype code, default is 101 for double-check LL, alternatively 100 (smallest available first-time LL), 102 (world-record-sized first-time LL), 104 (100M digit number to LL test - not recommended), 150 (smallest available first-time PRP), 151 (double-check PRP), 152 (world-record-sized first-time PRP), 153 (100M digit number to PRP test - not recommended)")

parser.add_option("-n", "--num_cache", dest="num_cache", type="int", default=1, help="Number of assignments to cache, default: %default")
parser.add_option("-L", "--percent_limit", dest="percent_limit", type="int", default=90, help="Add one to num_cache when current assignment is already done at this percentage, default: %default")

parser.add_option("-t", "--timeout", dest="timeout", type="int", default=60*60*6, help="Seconds to wait between network updates, default %default [6 hours]. Use 0 for a single update without looping.")

group = OptionGroup(parser, "Registering Options: send to mersenne.org when registering, visible in CPUs in the website.")
group.add_option("-r", "--register", action="store_true", dest="register", default=False, help="Register to mersenne.org, this allows sending regular updates and follow the progress on the website.")
group.add_option("-H", "--hostname", dest="hostname", default=platform.node()[:20], help="Hostname name for mersenne.org, default: %default")
# TODO: add detection for most parameter, including automatic change of the hardware
group.add_option("-c", "--cpu_model", dest="cpu_model", default="cpu.unknown", help="CPU model, defautl: %default")
group.add_option("--features", dest="features", default="", help="CPU features, default '%default'")
group.add_option("--frequency", dest="frequency", type="int", default=100, help="CPU frequency in MHz, default: %default")
group.add_option("-m", "--memory", dest="memory", type="int", default=0, help="memory size in MB, default: %default")
group.add_option("--L1", dest="L1", type="int", default=8, help="L1 cache size, default: %default")
group.add_option("--L2", dest="L2", type="int", default=512, help="L2 cache size, default: %default")
group.add_option("--np", dest="np", type="int", default=1, help="number of processors, default: %default")
group.add_option("--hp", dest="hp", type="int", default=0, help="number of hyperthreading cores (0 is unknown), default: %default")
parser.add_option_group(group)

(options, args) = parser.parse_args()

progname = os.path.basename(sys.argv[0])
workdir = os.path.expanduser(options.workdir)

localfile = os.path.join(workdir, "local.ini")
workfile = os.path.join(workdir, "worktodo.ini")
resultsfile = os.path.join(workdir, "results.txt")

# A cumulative backup
sentfile = os.path.join(workdir, "results_sent.txt")

# Good refs re. Python regexp: https://www.geeksforgeeks.org/pattern-matching-python-regex/, https://www.python-course.eu/re.php
# pre-v19 only handled LL-test assignments starting with either DoubleCheck or Test, followed by =, and ending with 3 ,number pairs:
#
#	workpattern = r"(DoubleCheck|Test)=.*(,[0-9]+){3}"
#
# v19 we add PRP-test support - both first-time and DC of these start with PRP=, the DCs tack on 2 more ,number pairs representing
# the PRP base to use and the PRP test-type (the latter is a bit complex to explain here). Sample of the 4 worktypes supported by v19:
#
#	Test=7A30B8B6C0FC79C534A271D9561F7DCC,89459323,76,1
#	DoubleCheck=92458E009609BD9E10577F83C2E9639C,50549549,73,1
#	PRP=BC914675C81023F252E92CF034BEFF6C,1,2,96364649,-1,76,0
#	PRP=51D650F0A3566D6C256B1679C178163E,1,2,81348457,-1,75,0,3,1
#
# and the obvious regexp pattern-modification is
#
#	workpattern = r"(DoubleCheck|Test|PRP)=.*(,[0-9]+){3}"
#
# Here is where we get to the kind of complication the late baseball-philosopher Yogi Berra captured via his aphorism,
# "In theory, theory and practice are the same. In practice, they're different". Namely, while the above regexp pattern
# should work on all 4 assignment patterns, since each has a string of at least 3 comma-separated nonnegative ints somewhere
# between the 32-hexchar assignment ID and end of the line, said pattern failed on the 3rd of the above 4 assignments,
# apparently because when the regexp is done via the 'greplike' below, the (,[0-9]+){3} part of the pattern gets implicitly
# tiled to the end of the input line. Assignment # 3 above happens to have a negative number among the final 3, thus the
# grep fails. This weird behavior is not reproducible running Python in console mode:
#
#	>>> import re
#	>>> s1 = "DoubleCheck=92458E009609BD9E10577F83C2E9639C,50549549,73,1"
#	>>> s2 = "Test=7A30B8B6C0FC79C534A271D9561F7DCC,89459323,76,1"
#	>>> s3 = "PRP=BC914675C81023F252E92CF034BEFF6C,1,2,96364649,-1,76,0"
#	>>> s4 = "PRP=51D650F0A3566D6C256B1679C178163E,1,2,81348457,-1,75,0,3,1"
#	>>> print re.search(r"(DoubleCheck|Test|PRP)=.*(,[0-9]+){3}" , s1)
#	<_sre.SRE_Match object at 0x1004bd250>
#	>>> print re.search(r"(DoubleCheck|Test|PRP)=.*(,[0-9]+){3}" , s2)
#	<_sre.SRE_Match object at 0x1004bd250>
#	>>> print re.search(r"(DoubleCheck|Test|PRP)=.*(,[0-9]+){3}" , s3)
#	<_sre.SRE_Match object at 0x1004bd250>
#	>>> print re.search(r"(DoubleCheck|Test|PRP)=.*(,[0-9]+){3}" , s4)
#	<_sre.SRE_Match object at 0x1004bd250>
#
# Anyhow, based on that I modified the grep pattern to work around the weirdness, by appending .* to the pattern, thus
# changing things to "look for 3 comma-separated nonnegative ints somewhere in the assignment, followed by anything",
# also now to specifically look for a 32-hexchar assignment ID preceding such a triplet, and to allow whitespace around
# the =. The latter bit is not needed based on current server assignment format, just a personal aesthetic bias of mine:
#
workpattern = re.compile("(DoubleCheck|Test|PRP)\s*=\s*([0-9A-F]{32})(,[0-9]+){3}.*")

# mersenne.org limit is about 4 KB; stay on the safe side
sendlimit = 3000 # TODO: enforce this limit

# adapted from http://stackoverflow.com/questions/923296/keeping-a-session-in-python-while-making-http-requests
primenet_cj = cookiejar.CookieJar()
primenet = build_opener(HTTPCookieProcessor(primenet_cj))

# If debug is requested, try importinh urllib_debug.
# Disabled debug if import is failing. This allows not distribuing urllib_debug module
# when it is not useful.
if options.debug > 1:
	# if urllib_debug is not present, don't try to activate the debugging
	try:
		import urllib_debug
	except ImportError:
		options.debug = 1

if options.debug == 3:
	debug_print("Enable testing url request and responses")
	from urllib_debug import TestHTTPHandler, TestHTTPSHandler
	primenet = build_opener(HTTPCookieProcessor(primenet_cj), TestHTTPHandler, TestHTTPSHandler)
	my_opener = build_opener(TestHTTPHandler, TestHTTPSHandler)
	install_opener(my_opener)
	from random import seed
	seed(3)
elif options.debug == 2:
	debug_print("Enable spying url request and responses")
	from urllib_debug import SpyHTTPHandler, SpyHTTPSHandler
	primenet = build_opener(HTTPCookieProcessor(primenet_cj), SpyHTTPHandler, SpyHTTPSHandler)
	my_opener = build_opener(SpyHTTPHandler, SpyHTTPSHandler)
	install_opener(my_opener)

# load local.ini and update options
config = config_read()
config_updated = merge_config_and_options(config, options)

# check options after merging so that if local.ini file is changed by hand,
# values are also checked
# TODO: check that input char are ascii or at least supported by the server
if not (8 <= len(options.cpu_model) <= 64):
	parser.error("cpu_model must be between 8 and 64 characters")
if options.hostname is not None and len(options.hostname) > 20:
	parser.error("hostname must be less than 21 characters")
if options.features is not None and len(options.features) > 64:
	parser.error("features must be less than 64 characters")

# write back local.ini if necessary
if config_updated:
	debug_print("write local.ini")
	config_write(config)

if options.register:
	# if guid already exist, recover it, this way, one can (re)register to change
	# the CPU model (changing instance name can only be done in the website)
	guid = get_guid(config)
	register_instance(guid)
	sys.exit(0)

if options.username is None or options.password is None:
	parser.error("Username and password must be given")

while True:
	# Log in to primenet
	try:
		login_data = OrderedDict((
			("user_login", options.username),
			("user_password", options.password),
		))

		# TODO: login only if necessary:
		# TODO: when configuration has been changed to test the password
		# TODO: when getting assignments is necessary
		# TODO: on a monthly basis ?
		# This makes a POST instead of GET
		data = urlencode(login_data).encode('utf-8')
		r = primenet.open(primenet_baseurl + "default.php", data)
		if not (options.username + "<br>logged in").encode('utf-8') in r.read():
			primenet_login = False
			debug_print("ERROR: Login failed.")
		else:
			primenet_login = True
	except URLError:
		debug_print("Primenet URL open ERROR")

	if primenet_login:
		submit_work()
		progress = update_progress()
		got = get_assignment(progress)
		if got > 0:
			debug_print("Redo progress update to update the just obtained assignment")
			# Since assignment are obtain by manual assignment, it is important to update them
			# to mark them as belonging to the current computer.
			update_progress()
	if options.timeout <= 0:
		break
	try:
		sleep(options.timeout)
	except KeyboardInterrupt:
		break

sys.exit(0)

# vim: noexpandtab ts=4 sts=0 sw=0
