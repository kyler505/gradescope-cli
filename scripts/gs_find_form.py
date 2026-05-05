from gscli import login_connection
_, conn = login_connection(None, None)
url = 'https://www.gradescope.com/courses/1200912/assignments/7637102'
resp = conn.session.get(url)
text = resp.text
for needle in ['/submissions', 'multipart/form-data', 'type="file"', 'file_input', 'Choose Files', 'Upload Files', 'submission']:
    idx = text.find(needle)
    print('NEEDLE', needle, 'idx', idx)
    if idx != -1:
        print(text[max(0, idx-400):idx+1200])
        print('\n---\n')
