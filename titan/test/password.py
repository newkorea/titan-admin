import uuid
import hashlib

def hashText(text):
    salt = uuid.uuid4().hex
    return hashlib.sha256(salt.encode() + text.encode()).hexdigest() + ':' + salt

text = '1'
print(hashText(text))