
from hashlib import md5

from random import getrandbits
def add_secure_v5_args(args, guid, salt=None):
	"""Add sh and ss arguments given a random salt (to sh) and the key derived from guid.
	guid must be a 32-byte hexa string, as used in the 'g' args of V5 API
	>>> add_secure_v5_args("v=0.95&px=GIMPS&t=ap&g=0807e4456339466376bcf63436fe5176&k=51D7100698D8B18893B7BE2AB5FDCEBC&stage=LL&c=0&p=83.0492&d=86400&e=1268735&iteration=85000000&res64=9CE24584CD974BF0&ec=00000000", "0807e4456339466376bcf63436fe5176", 40830)
	'v=0.95&px=GIMPS&t=ap&g=0807e4456339466376bcf63436fe5176&k=51D7100698D8B18893B7BE2AB5FDCEBC&stage=LL&c=0&p=83.0492&d=86400&e=1268735&iteration=85000000&res64=9CE24584CD974BF0&ec=00000000&ss=40830&sh=DF7FD29CA068A0ED1843F4BB85840F3B'
"""
	# derive the key
	h = bytearray(md5(guid.encode('ascii')).digest()) # h is 16 bytes long bytearray(), which is mutable unlike bytes(), guid must be ASCII char, fail if it isn't
	for i in range(16):
		d = c = h[i]
		c = (c^0x49)&0xf
		d = (d ^ 0x45) ^ h[c]
		h[i] = d # mutability used
	key = md5(bytes(h)).hexdigest().upper() # the bytes() convertion is necessary for python2.6 and before
	if salt is None:
		salt = getrandbits(16)
	args += "&ss="+str(salt)+"&"
	args_to_hash= args+key
	sh = md5(args_to_hash.encode("utf-8")).hexdigest().upper()
	# Note that ss and sh args MUST be the last ones in the url, in this order
	return args+"sh="+sh

def SEC1(p):
	"""
	>>> SEC1(10388359)
	'A49D230E'
	"""
	ans = p%27951 + p%88311 + (((p%19019 + p%63111)&0xffff) <<16)
	return "{:08X}".format(ans%0xffffffff)

# SEC3(157257439)=E55A1685
# SEC3(173084057)=7D4D7FD1

def SEC2(shift_count,error_count,res64,p):
	"""
	>>> SEC2(43751873,0,0x5388B3DB11E4A27C,52935359)
	'8B37F9C1'
	>>> SEC2(27224212,0,0x8D1346B59440C81D,46481819)
	'F50E12E8'
	>>> SEC2(66890488,0,0xCAF1457F2C31A6D5,81686569)
	'F187246E,,00000000,'
	"""
	high32 = res64>>32
	low32 = res64&0xffffffff
	a0 = shift_count+error_count+high32+low32
	a1 = p%4219 + p%91631 + ((p%15923+p%62071)<<16)
	ans = a0^a1
	return "{:08X}".format(ans%0xffffffff)

if __name__ == "__main__":
	import doctest
	doctest.testmod()
