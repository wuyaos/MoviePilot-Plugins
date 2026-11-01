"""猪猪公开前端 SRP 协议：2048-bit group、PBKDF2-SHA256、A/M1/M2。

无网络或持久化；不实现明文密码降级。随机私钥每次握手重新生成。
"""
import hashlib
import secrets

N_HEX = (
    'AC6BDB41324A9A9BF166DE5E1389582FAF72B6651987EE07FC3192943DB56050A'
    '37329CBB4A099ED8193E0757767A13DD52312AB4B03310DCD7F48A9DA04FD50E'
    '8083969EDB767B0CF6095179A163AB3661A05FBD5FAAAE82918A9962F0B93B855F'
    '97993EC975EEAA80D740ADBF4FF747359D041D5C33EA71D281E446B14773BCA97B'
    '43A23FB801676BD207A436C6481F1D2B9078717461A5B9D32E688F87748544523B'
    '524B0D57D5EA77A2775D2ECFA032CFBDBF52FB3786160279004E57AE6AF874E730'
    '3CE53299CCC041C7BC308D82A5698F3A8D0C38271AE35F8E9DBFBB694B5C803D'
    '89F7AE435DE236D525F54759B65E372FCD68EF20FA7111F9E4AFF73'
)
N = int(N_HEX, 16)
WIDTH = len(N_HEX) // 2


def _hash(*parts):
    return hashlib.sha256(b''.join(parts)).digest()


def _pad(value):
    return value.to_bytes(WIDTH, 'big')


def proof(identity, password, salt_hex, public_hex, *, private=None):
    salt = bytes.fromhex(salt_hex)
    public = int(public_hex, 16)
    if not salt or len(salt) > 256 or not 0 < public < N:
        raise ValueError('invalid SRP challenge')
    private = private if private is not None else (secrets.randbits(256) or 1)
    derived = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 210000, 32)
    x = int.from_bytes(_hash(salt, _hash((identity + ':').encode(), derived)), 'big')
    a = pow(2, private, N)
    u = int.from_bytes(_hash(_pad(a), _pad(public)), 'big')
    if u == 0:
        raise ValueError('invalid SRP u')
    k = int.from_bytes(_hash(bytes.fromhex(N_HEX), _pad(2)), 'big')
    shared = pow((public - k * pow(2, x, N)) % N, private + u * x, N)
    key = _hash(_pad(shared))
    xor = bytes(a ^ b for a, b in zip(_hash(bytes.fromhex(N_HEX)), _hash(_pad(2))))
    m1 = _hash(xor, _hash(identity.encode()), salt, _pad(a), _pad(public), key)
    return {'a': _pad(a).hex(), 'm1': m1.hex(), 'm2': _hash(_pad(a), m1, key).hex()}
