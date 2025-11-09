from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_OAEP
from Crypto import Random


PRIVATE_KEY = '''-----BEGIN PRIVATE KEY-----
MIICdwIBADANBgkqhkiG9w0BAQEFAASCAmEwggJdAgEAAoGBAKH4mRiary9V4j4OalYeEqE/nHdR
4Mi6OShUMAWY9EILF9ZzBb4ZYxuKANbvmUvnU03zQRXoK+R5jdPPMyubX9qBMGkQe6yPHcsuqqVi
z+YBzb0tLf9j1w/x5m6umvbPM8C2dIOEpWLSghXzv7/3T5vVGXOdx3QASpcm3A5vRVupAgMBAAEC
gYBqQyKN1c3hDENl2ydAYHJwf78zOPB0QFiHcNQgl/yH56c39jZqRVWUF7H9USwNdDJfDZxBtxQ0
zNqTf3hev4zeTdl5qmnQu1b05vaUwHNUb8kCu9TEqgON8EiGhbnCccYLz/bS80+TuvVFnDnVnhlM
ZApt7xm/GswHwOucUiLcAQJBANogJa2XrdvRlN3U3jsRehLPH6xupVVRGyP+HWqI3uojhLMrCNk8
N2DP6rZeZUQNoJMsOhm5Zu3XnRp35x4a90kCQQC+GFb812a498IzVHU1pujm+9ZrJi/is0FBVG0X
9iHUMtqLjCWoLjr7IhPkGMaENBTye6Iz3iTEE0SopyQdg2FhAkEAn47MgQNnRlk1EGBaf9L0/TVN
8hCuGI7Pz7BfTEL67UM2Gunr+xy1VbhB9U1vvixJvd6oUZDx3iHO5kG3aqpHIQJAPv9j/KEJ+uyo
4EfyHBi3gK0fLx1Vq0SKsLLhAJriNSexQ6PrauP/SfDONL59M5zrAD020QeimZRlIZtanalHoQJB
AJFFz7CkLQ3Zy8c24A6SJIJmBNNErPH5K3NphkQihmEcS1TldSmT8D4iB5wDNm9f5MNxg6gYqXnR
1LDacOM+KSA=
-----END PRIVATE KEY-----
'''

PUBLIC_KEY = '''-----BEGIN PUBLIC KEY-----
MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQDmwwFxxkClvsBzZUtE0CN4S7P0QWZxnpxn2De0
zlqbjY6Put/8738SXYkGsuBIb5QZU3tDb/0hmON3zQ84BLexksP2iNqY1q1VSeY2NkV/QxrCUefU
edTFsDU+ZcIB5JJ02m4fqpYtzYowtf5JrgjYHcyrO1IaX3NVITm9EPOMHQIDAQAB
-----END PUBLIC KEY-----
'''

print('PRIVATE_KEY -> ', PRIVATE_KEY)
print('PUBLIC_KEY -> ', PUBLIC_KEY)

private = RSA.importKey(PRIVATE_KEY)
public  = RSA.importKey(PUBLIC_KEY)

print('private -> ', private)
print('public -> ', public)

msg = b'hello world'
print('msg -> ', msg)

cipher = PKCS1_OAEP.new(public)
enc_msg = cipher.encrypt(msg)
print('enc_msg -> ', enc_msg)

cipher = PKCS1_OAEP.new(private)
dec_msg = cipher.decrypt(enc_msg)
print("dec_msg ->", dec_msg)
