from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_OAEP
from Crypto import Random


key = RSA.generate(1024)
PRIVATE_KEY = key.exportKey('PEM')
PUBLIC_KEY = key.publickey().exportKey('PEM')

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
