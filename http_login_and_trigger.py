import requests
s = requests.Session()
login_url = 'http://127.0.0.1:8000/auth/login'
# The login form fields may be 'username' and 'password'
payload = {'username':'admin','password':'password'}
resp = s.post(login_url, data=payload, allow_redirects=True)
print('LOGIN_STATUS', resp.status_code)
open('login_response.html','wb').write(resp.content)
# Now call the manual sync trigger
trigger_url = 'http://127.0.0.1:8000/api/database/sync/trigger'
resp2 = s.post(trigger_url)
print('TRIGGER_STATUS', resp2.status_code)
open('trigger_with_auth.json','wb').write(resp2.content)
