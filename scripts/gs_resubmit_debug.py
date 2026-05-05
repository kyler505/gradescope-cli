from pathlib import Path
import mimetypes
from bs4 import BeautifulSoup
from requests_toolbelt.multipart.encoder import MultipartEncoder
from gscli import login_connection

course_id = '1200912'
assignment_id = '7637102'
current_submission_id = '411206047'
_, conn = login_connection(None, None)
page_url = f'https://www.gradescope.com/courses/{course_id}/assignments/{assignment_id}/submissions/{current_submission_id}'
resp = conn.session.get(page_url)
print('page_get', resp.status_code, resp.url)
soup = BeautifulSoup(resp.text, 'html.parser')
form = soup.find('form', {'class': 'js-submitCodeForm'})
print('form_action', form.get('action'))
auth_token = form.find('input', {'name': 'authenticity_token'})['value']
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
    headers = {'Content-Type': multipart.content_type, 'Referer': page_url}
    post_url = f'https://www.gradescope.com{form.get("action")}'
    resp2 = conn.session.post(post_url, data=multipart, headers=headers)
    print('post', resp2.status_code, resp2.url)
    print(resp2.text[:2000])
finally:
    for h in handles:
        h.close()
