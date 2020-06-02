
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
	>>> SEC1(10391921)
	'C0713EE2'
	>>> SEC1(10391923)
	'C0753EE6'
	>>> SEC1(10391933)
	'C0893EFA'
	>>> SEC1(10391977)
	'C0E13F52'
	"""
	ans = p%27951 + p%88311 + (((p%19019 + p%63111)&0xffff) <<16)
	return "{:08X}".format(ans%0xffffffff)

def SEC2(shift_count,error_count,res64,p):
	"""
	>>> SEC2(27224212,00000000,0x8D1346B59440C81D,46481819)
	'F50E12E8'
	>>> SEC2(38144367,00000000,0x56C1D26E17D884E4,46481863)
	'A8B50527'
	>>> SEC2(2222140,00000000,0x69C1534F1C8DC294,45474227)
	'4A2D97C7'
	>>> SEC2(4565789,00000000,0xE28A2B7FE98A6D94,45475687)
	'1B9F3170'
	>>> SEC2(79015339,00000000,0x1B30A053FEBFE8C6,81686573)
	'140685EE'
	>>> SEC2(66890488,00000000,0xCAF1457F2C31A6D5,81686569)
	'F187246E'
	>>> SEC2(55870980,00000000,0xBAF66B0BF618D25B,82691087)
	'88046425'
	>>> SEC2(72624900,00000000,0x31C89B3679E466F8,82727119)
	'6983014E'
	>>> SEC2(37624106,00000000,0xF6AEA4794305A3BD,44812727)
	'C65F7FB8'
	>>> SEC2(62387410,00000000,0x6038A55C8455541E,84718061)
	'05B3272A'
	>>> SEC2(47979404,00000000,0xE3B1C46813C0ED0D,83560753)
	'9F269433'
	>>> SEC2(78942450,00000000,0x0732BD1652CACDD6,86048513)
	'179A38EA'
	>>> SEC2(30095288,00000000,0xF0E845FBEE029FAB,86198053)
	'240E11E2'
	>>> SEC2(1468244,00000000,0x7B7DDEC90A24B14B,49707187)
	'747B4395'
	>>> SEC2(10851302,00000000,0x31E8839361D952E9,48557959)
	'FE45381A'
	>>> SEC2(55890158,00000000,0xBA08EC4F80D40908,87151093)
	'20C2F2C4'
	>>> SEC2(82413708,00000000,0x0997DDBA027429BF,88420601)
	'6B35F4C2'
	>>> SEC2(55487474,00000000,0xCEECA42DF4CA4145,88783187)
	'424DC509'
	>>> SEC2(12561072,00000000,0x639CECC486E8FD22,90988493)
	'0D03F326'
	>>> SEC2(27609823,00000000,0xB339D6BE8545AAA7,91378813)
	'63B8AB75'
	>>> SEC2(64982,00000000,0xB891C17502F8A985,91700491)
	'29E17951'
	>>> SEC2(415798,00000000,0x713CEA8487C564A5,92129717)
	'82130BFC'
	>>> SEC2(43751873,00000000,0x5388B3DB11E4A27C,52935359)
	'8B37F9C1'
	"""
	high32 = res64>>32
	low32 = res64&0xffffffff
	a0 = (shift_count+error_count+high32+low32)&0xffffffff
	a1 = (p%4219 + p%91631 + ((p%15923+p%62071)<<16))%0xffffffff
	ans = a0^a1
	return "{:08X}".format(ans)

def SEC3(p):
    """
	>>> SEC3(157257439)
	'E55A1685'
	>>> SEC3(173084057)
	'7D4D7FD1'
	>>> SEC3(173084047)
	'7D437FD2'
	>>> SEC3(173084069)
	'7D3C7FD2'
	>>> SEC3(173084077)
	'7D457FCF'
	>>> SEC3(173084231)
	'7D4E7FCF'
    """

if __name__ == "__main__":
	import doctest
	doctest.testmod()
