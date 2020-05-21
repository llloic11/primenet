
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

if __name__ == "__main__":
	import doctest
	doctest.testmod()

