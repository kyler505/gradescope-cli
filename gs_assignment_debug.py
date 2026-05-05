from gscli import login_connection
_, conn = login_connection(None, None)
url = 'https://www.gradescope.com/courses/1200912/assignments/7637102'
resp = conn.session.get(url)
print('status', resp.status_code, resp.url)
text = resp.text
for needle in ['submission[files]', 'submission[method]', 'Upload', 'submit', 'pred.csv', 'csv']:
    idx = text.lower().find(needle.lower())
    print('\nNEEDLE', needle, 'idx', idx)
    if idx != -1:
        print(text[max(0, idx-500):idx+1500])
