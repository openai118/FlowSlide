import requests, json
s = requests.Session()
login_url = 'http://127.0.0.1:8000/auth/login'
resp = s.post(login_url, data={'username':'admin','password':'password'}, allow_redirects=True)
print('LOGIN', resp.status_code)
resp2 = s.get('http://127.0.0.1:8000/api/database/sync/status')
open('sync_status.json','wb').write(resp2.content)
print('STATUS', resp2.status_code)
