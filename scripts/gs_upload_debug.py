from pathlib import Path
import mimetypes
from bs4 import BeautifulSoup
from requests_toolbelt.multipart.encoder import MultipartEncoder
from gscli import login_connection
from gradescopeapi.classes.submission import DEFAULT_GRADESCOPE_BASE_URL

course_id = '1200912'
assignment_id = '7637102'
_, conn = login_connection(None, None)
GS_COURSE_ENDPOINT = f"{DEFAULT_GRADESCOPE_BASE_URL}/courses/{course_id}"
GS_UPLOAD_ENDPOINT = f"{DEFAULT_GRADESCOPE_BASE_URL}/courses/{course_id}/assignments/{assignment_id}/submissions"
resp = conn.session.get(GS_COURSE_ENDPOINT)
print('course_get', resp.status_code, resp.url)
soup = BeautifulSoup(resp.text, 'html.parser')
auth_token = soup.find('meta', {'name': 'csrf-token'})['content']
fields = [
    ('utf8', '✓'),
    ('authenticity_token', auth_token),
    ('submission[method]', 'upload'),
]
files = [
    Path('/Users/kcao/dev/gradescope-api/test01-pred.csv'),
    Path('/Users/kcao/dev/gradescope-api/test02-pred.csv'),
    Path('/Users/kcao/dev/gradescope-api/test03-pred.csv'),
]
handles = []
try:
    for file in files:
        h = file.open('rb')
        handles.append(h)
        fields.append(('submission[files][]', (file.name, h, mimetypes.guess_type(file.name)[0])))
    multipart = MultipartEncoder(fields=fields)
    headers = {'Content-Type': multipart.content_type, 'Referer': GS_COURSE_ENDPOINT}
    resp2 = conn.session.post(GS_UPLOAD_ENDPOINT, data=multipart, headers=headers)
    print('post', resp2.status_code, resp2.url)
    print(resp2.text[:2000])
finally:
    for h in handles:
        h.close()
