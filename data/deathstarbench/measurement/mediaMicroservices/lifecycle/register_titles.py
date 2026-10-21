import sys, time, urllib.parse, urllib.request, urllib.error
seen = set()
for i, title in enumerate(sys.stdin.read().splitlines(), 1):
    if title in seen:
        continue
    seen.add(title)
    data = urllib.parse.urlencode({'title': title, 'movie_id': str(i)}).encode()
    for attempt in range(5):
        try:
            urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:8080/wrk2-api/movie/register', data=data), timeout=5).read()
            break
        except urllib.error.HTTPError as e:
            if e.code == 500:
                break
            if attempt == 4:
                print('HTTP ERROR', i, title, e.code, repr(e))
                raise
        except Exception as e:
            if attempt < 4:
                time.sleep(0.5)
            else:
                print('ERROR', i, title, repr(e))
                raise
print('registered', len(seen))
