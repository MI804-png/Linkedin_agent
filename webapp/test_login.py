import urllib.request, urllib.parse, http.cookiejar

jar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

data = urllib.parse.urlencode({'email': 'mikhael.nabil.salama.rezk@gmail.com', 'password': 'Nabil@2003'}).encode()
req = urllib.request.Request('http://localhost:5001/login', data=data, method='POST')
try:
    r = opener.open(req, timeout=10)
    print(f'Login resp: {r.status}, URL: {r.url}')
    print(f'Has session: {any(c.name == "session" for c in jar)}')
except urllib.error.HTTPError as e:
    loc = e.headers.get('Location', '')
    print(f'HTTPError: {e.code}, Location: {loc}')
    print(f'Has session: {any(c.name == "session" for c in jar)}')

# Now try dashboard
try:
    r2 = opener.open('http://localhost:5001/dashboard', timeout=10)
    body = r2.read().decode()
    if 'speedometer' in body:
        print(f'SUCCESS: Dashboard loaded, length={len(body)}')
    else:
        print(f'FAIL: final URL={r2.url}, body start={body[:200]}')
except urllib.error.HTTPError as e:
    print(f'Dashboard HTTPError: {e.code}')
