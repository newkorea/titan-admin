
import hashlib
import uuid

def hashText(text):
    salt = uuid.uuid4().hex
    return hashlib.sha256(salt.encode() + text.encode()).hexdigest() + ':' + salt

def matchHashedText(hashedText, providedText):
    try:
        _hashedText, salt = hashedText.split(':')
        return _hashedText == hashlib.sha256(salt.encode() + providedText.encode()).hexdigest()
    except ValueError:
        return False

# Test
pw = "mysecretpassword"
hashed = hashText(pw)
print(f"Password: {pw}")
print(f"Hashed: {hashed}")

print(f"Match correct: {matchHashedText(hashed, pw)}")
print(f"Match wrong: {matchHashedText(hashed, 'wrong')}")
print(f"Match empty: {matchHashedText(hashed, '')}")

# Test malformed hash
print(f"Match malformed: {matchHashedText('invalidhash', pw)}")
