import urllib.request, json

data = json.dumps({'name': 'Test', 'email': 'test@test.com', 'password': 'password123'}).encode('utf-8')
req = urllib.request.Request('http://127.0.0.1:8000/api/auth/register', data=data, headers={'Content-Type': 'application/json'})

try:
    res = urllib.request.urlopen(req)
    print("SUCCESS:", res.read().decode('utf-8'))
except Exception as e:
    print("ERROR:", getattr(e, 'read', lambda: b'No body')().decode('utf-8'))
