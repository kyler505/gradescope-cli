from gscli import login_connection
_, conn = login_connection(None, None)
url = 'https://www.gradescope.com/courses/1200912/assignments/7637102/submissions/411206047'
resp = conn.session.get(url)
text = resp.text
idx = text.find('js-submitCodeForm')
print(text[idx-1000:idx+4000])
