import requests

url = 'https://fcm.googleapis.com/fcm/send'

headers = {
    "Authorization": "key=AAAAHkOoqDo:APA91bEv8Q51tDZQ5rMgDTWStGQK_s0W1jAkfB0a29aY0BTPamiYwxHGPAxue0UoJz8tZ_ERfSry-QvFBtDO5Akw2N6BI2myDUXDXUiZP6FCHj9-p0zp_oEOcNBx2IXcTA7zC8ChMJNy",
    "Content-Type": "application/json"
}
payload = {
     "to" : "/topics/all",
     "collapse_key" : "type_a",
     "data" : {
         "body" : "world",
         "title": "hello"
     }
}

r = requests.post(url, json=payload, headers=headers)
print(r.status_code)
print(r.text)