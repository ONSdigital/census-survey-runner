import logging;logging.basicConfig(
    format='%(asctime)s %(levelname)-8s %(message)s',
    level=logging.ERROR,
    datefmt='%Y-%m-%d %H:%M:%S')

import datetime
from asyncio import ensure_future

import backoff
from aiohttp import web, ClientSession, ClientResponseError, TCPConnector
from gcloud.aio.auth import Token
from gcloud.aio.storage import Storage

from jinja2 import Environment, FileSystemLoader, select_autoescape

import os
import ujson
from uuid import uuid4

import yaml
from jwcrypto import jwe
from sdc.crypto.decrypter import decrypt
from sdc.crypto.key_store import KeyStore

from app.authentication.user_id_generator import UserIDGenerator
from app.keys import KEY_PURPOSE_AUTHENTICATION
from app.storage.metadata_parser import parse_runner_claims
from app.storage.storage_encryption import StorageEncryption


storage_backend = os.getenv('EQ_STORAGE_BACKEND')
if storage_backend == 'gcs':
    class ComputeEngineToken(Token):

        def __init__(self, project, session=None):
            self.project = project

            self.session = session

            self.access_token = None
            self.access_token_duration = None
            self.access_token_acquired_at = None

            self.acquiring = None

        async def get(self):
            await self.ensure_token()
            return self.access_token

        async def ensure_token(self):
            if self.acquiring:
                await self.acquiring
                return

            if not self.access_token:
                self.acquiring = ensure_future(self.acquire_access_token())
                await self.acquiring
                return

            now = datetime.datetime.now()
            delta = (now - self.access_token_acquired_at).total_seconds()
            if delta <= self.access_token_duration / 2:
                return

            self.acquiring = ensure_future(self.acquire_access_token())
            await self.acquiring

        @backoff.on_exception(backoff.expo, Exception, max_tries=5)
        async def acquire_access_token(self):
            if not self.session:
                self.session = ClientSession(conn_timeout=10, read_timeout=10)

            headers = {'metadata-flavor': 'Google'}
            resp = await self.session.get('http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token', headers=headers, timeout=10)
            resp.raise_for_status()
            content = await resp.json()

            self.access_token = str(content['access_token'])
            self.access_token_duration = int(content['expires_in'])
            self.access_token_acquired_at = datetime.datetime.now()
            self.acquiring = None
            return True

    project = os.getenv('GOOGLE_CLOUD_PROJECT')
    session = ClientSession(connector=TCPConnector(limit=int(os.getenv('EQ_GCS_MAX_POOL_CONNECTIONS', '30'))))
    creds = os.getenv('EQ_GCS_CREDENTIALS', 'META')
    if creds == 'META':
        token = ComputeEngineToken(project, session=session)
        storage = Storage(project, None, token=token, session=session)
    else:
        storage = Storage(project, creds, session=session)


    @backoff.on_exception(backoff.expo, Exception, max_tries=10)
    async def get_answers(user_id, key):
        try:
            data = await storage.download_as_string(os.getenv('EQ_GCS_BUCKET_ID'), 'flat/' + user_id)
            return decrypt_data(key, data)
        except ClientResponseError as e:
            if e.status == 404:
                return {}

            raise e


    @backoff.on_exception(backoff.expo, Exception, max_tries=10)
    async def put_answers(user_id, answers, key):
        await storage.upload(os.getenv('EQ_GCS_BUCKET_ID'), 'flat/' + user_id, encrypt_data(key, answers))
else:
    storage = {}

    async def get_answers(user_id, key):
        return decrypt_data(key, storage[user_id]) if user_id in storage else {}

    async def put_answers(user_id, answers, key):
        storage[user_id] = encrypt_data(key, answers)

with open(os.getenv('EQ_KEYS_FILE', 'keys.yml')) as f:
    key_store = KeyStore(yaml.safe_load(f))

with open(os.getenv('EQ_SECRETS_FILE', 'secrets.yml')) as secrets_file:
    secrets = yaml.safe_load(secrets_file)['secrets']


routes = web.RouteTableDef()

id_generator = UserIDGenerator(10000, secrets['EQ_SERVER_SIDE_STORAGE_USER_ID_SALT'], secrets['EQ_SERVER_SIDE_STORAGE_USER_IK_SALT'])

env = Environment(
    loader=FileSystemLoader('flat_templates'),
    autoescape=select_autoescape(['html', 'xml'])
)

PEPPER = secrets['EQ_SERVER_SIDE_STORAGE_ENCRYPTION_USER_PEPPER']

INT_ANSWERS = {
    'overnight-visitors-answer',
    'number-of-bedrooms-answer',
    'number-of-vehicles-answer'
}

LIST_ANSWERS = {
    'central-heating-answer',
    'national-identity-england-answer',
    'religion-answer',
    'passports-answer',
    'qualifications-england-answer',
    'employment-type-answer',
    'occupation-answer'
}

MEMBERS_PAGES = [
    'introduction',
    'permanent-or-family-home',
    'household-composition',
    'everyone-at-address-confirmation',
    'overnight-visitors',
    'household-relationships',
    'completed'
]

HOUSEHOLD_PAGES = [
    'introduction',
    'type-of-accommodation',
    'type-of-house',
    'self-contained-accommodation',
    'number-of-bedrooms',
    'central-heating',
    'own-or-rent',
    'number-of-vehicles',
    'completed'
]

MEMBER_PAGES = [
    'introduction',
    'details-correct',
    'over-16',
    'private-response',
    'sex',
    'date-of-birth',
    'marital-status',
    'another-address',
    'other-address',
    'address-type',
    'in-education',
    'term-time-location',
    'country-of-birth',
    'carer',
    'national-identity',
    'ethnic-group',
    'other-ethnic-group',
    'language',
    'religion',
    'past-usual-address',
    'passports',
    'disability',
    'qualifications',
    'employment-type',
    'jobseeker',
    'job-availability',
    'job-pending',
    'occupation',
    'ever-worked',
    'main-job',
    'hours-worked',
    'work-travel',
    'job-title',
    'job-description',
    'main-job-type',
    'business-name',
    'employers-business',
    'completed'
]

VISITOR_PAGES = [
    'name',
    'sex',
    'date-of-birth',
    'uk-resident',
    'address',
    'completed'
]


@routes.get('/session')
async def create_session(request):
    decrypted_token = decrypt(token=request.query['token'], key_store=key_store, key_purpose=KEY_PURPOSE_AUTHENTICATION, leeway=120)

    # TODO validate JTI

    claims = parse_runner_claims(decrypted_token)

    user_id = id_generator.generate_id(claims)
    user_ik = id_generator.generate_ik(claims)

    resp = redirect(request, '/introduction')
    resp.set_cookie('user_id', user_id)
    resp.set_cookie('user_ik', user_ik)
    raise resp


@routes.get('/fake_session')
async def create_fake_session(request):
    resp = redirect(request, '/introduction')
    resp.set_cookie('user_id', str(uuid4()))
    resp.set_cookie('user_ik', str(uuid4()))
    raise resp


@routes.post('/introduction')
async def handle_introduction_post(request):
    answers = await parse_answers(request, 0)
    await update_answers(request, answers)
    raise redirect(request, '/address')


@routes.get('/introduction')
async def handle_introduction(request):
    return render_template('introduction.html')


@routes.post('/address')
async def handle_address_post(request):
    answers = await parse_answers(request, 0)
    await update_answers(request, answers)
    raise redirect(request, '/members/introduction')


@routes.get('/address')
async def handle_address(request):
    return render_template('address.html')


@routes.post('/members/{page}')
async def handle_members_post(request):
    page = request.match_info['page']

    if page == 'household-composition':
        answers = {}
        data = await request.post()
        for k, v in data.items():
            if k.startswith('household-'):
                _, answer_instance, k = k.split('-', 2)
                answer_instance = int(answer_instance)
                answers[ak(k, answer_instance, 0)] = v
    elif page == 'household-relationships':
        answers = {}
        data = await request.post()
        for k, v in data.items():
            if k.startswith('household-relationships-answer-'):
                _, answer_instance = k.rsplit('-', 1)
                answer_instance = int(answer_instance)
                answers[ak('household-relationships-answer', answer_instance, 0)] = v
    else:
        answers = await parse_answers(request, 0)

    await update_answers(request, answers)
    i = MEMBERS_PAGES.index(page) + 1
    raise redirect(request, '/household/introduction' if i >= len(MEMBERS_PAGES) else '/members/{}'.format(MEMBERS_PAGES[i]))


@routes.get('/members/{page}')
async def handle_members(request):
    page = request.match_info['page']

    storage_key = StorageEncryption._generate_key(request.cookies['user_id'], request.cookies['user_ik'], PEPPER)
    answers = await get_answers(request.cookies['user_id'], storage_key)

    first_names = [v for (k, v) in answers.items() if k.startswith('first-name-')]
    middle_names = [v for (k, v) in answers.items() if k.startswith('middle-names-')]
    last_names = [v for (k, v) in answers.items() if k.startswith('last-name-')]
    members = [' '.join(n) for n in zip(first_names, middle_names, last_names)]

    address_line_1 = answers[ak('address-line-1', 0, 0)]

    return render_template('members/{}.html'.format(page), members=members, address_line_1=address_line_1)


@routes.post('/household/{page}')
async def handle_household_post(request):
    page = request.match_info['page']

    answers = await parse_answers(request, 0)
    await update_answers(request, answers)
    i = HOUSEHOLD_PAGES.index(page) + 1
    raise redirect(request, '/member/0/introduction' if i >= len(HOUSEHOLD_PAGES) else '/household/{}'.format(HOUSEHOLD_PAGES[i]))


@routes.get('/household/{page}')
async def handle_household(request):
    page = request.match_info['page']

    return render_template('household/{}.html'.format(page))


@routes.post('/member/{group_instance}/{page}')
async def handle_member_post(request):
    group_instance = int(request.match_info['group_instance'])
    page = request.match_info['page']

    if page == 'date-of-birth':
        answers = await parse_date(request, 'date-of-birth-answer', group_instance)
    else:
        answers = await parse_answers(request, group_instance)

    answers = await update_answers(request, answers)

    if page == 'private-response':
        data = await request.post()
        if data['private-response-answer'].startswith('Yes'):
            raise redirect(request, '/member/{}/request-private-response'.format(group_instance))

    if page == 'request-private-response':
        raise redirect(request, '/member/{}/completed'.format(group_instance))

    i = MEMBER_PAGES.index(page) + 1
    if i < len(MEMBER_PAGES):
        raise redirect(request, '/member/{}/{}'.format(group_instance, MEMBER_PAGES[i]))

    num_members = len([a for a in answers.keys() if a.startswith('first-name-')])

    group_instance += 1

    raise redirect(request, '/visitors_introduction' if group_instance >= num_members else '/member/{}/introduction'.format(group_instance))


@routes.get('/member/{group_instance}/{page}')
async def handle_member(request):
    group_instance = int(request.match_info['group_instance'])
    page = request.match_info['page']

    storage_key = StorageEncryption._generate_key(request.cookies['user_id'], request.cookies['user_ik'], PEPPER)
    answers = await get_answers(request.cookies['user_id'], storage_key)

    first_name = answers[ak('first-name', group_instance, 0)]
    middle_names = answers[ak('middle-names', group_instance, 0)]
    last_name = answers[ak('last-name', group_instance, 0)]

    return render_template('member/{}.html'.format(page), first_name=first_name, middle_names=middle_names, last_name=last_name)


@routes.post('/visitors_introduction')
async def handle_visitors_introduction_post(request):
    answers = await parse_answers(request, 0)
    await update_answers(request, answers)
    raise redirect(request, '/visitor/0/name')


@routes.get('/visitors_introduction')
async def handle_visitors_introduction(request):
    return render_template('visitors_introduction.html')


@routes.post('/visitor/{group_instance}/{page}')
async def handle_visitor_post(request):
    group_instance = int(request.match_info['group_instance'])
    page = request.match_info['page']

    if page == 'date-of-birth':
        answers = await parse_date(request, 'visitor-date-of-birth-answer', group_instance)
    else:
        answers = await parse_answers(request, group_instance)

    answers = await update_answers(request, answers)

    i = VISITOR_PAGES.index(page) + 1
    if i < len(VISITOR_PAGES):
        raise redirect(request, '/visitor/{}/{}'.format(group_instance, VISITOR_PAGES[i]))

    num_visitors = answers[ak('overnight-visitors-answer', 0, 0)]

    group_instance += 1

    raise redirect(request, '/visitors_completed' if group_instance >= num_visitors else '/visitor/{}/name'.format(group_instance))


@routes.get('/visitor/{group_instance}/{page}')
async def handle_visitor(request):
    group_instance = int(request.match_info['group_instance'])
    page = request.match_info['page']

    return render_template('visitor/{}.html'.format(page), group_instance=group_instance)


@routes.post('/visitors_completed')
async def handle_visitors_completed_post(request):
    answers = await parse_answers(request, 0)
    await update_answers(request, answers)
    raise redirect(request, '/completed')


@routes.get('/visitors_completed')
async def handle_visitors_completed(request):
    return render_template('visitors_completed.html')


@routes.post('/completed')
async def handle_completed_post(request):
    print('Submitting answers')
    # TODO validate and submit answers
    raise redirect(request, '/thank-you')


@routes.get('/completed')
async def handle_completed(request):
    return render_template('completed.html')


@routes.get('/thank-you')
async def handle_thank_you(request):
    return render_template('thank-you.html')


@routes.get('/dump/submission')
async def get_submission(request):
    storage_key = StorageEncryption._generate_key(request.cookies['user_id'], request.cookies['user_ik'], PEPPER)
    answers = await get_answers(request.cookies['user_id'], storage_key)

    flat_answers = []

    for k, v in answers.items():
        answer_id, answer_instance, group_instance = k.rsplit('-', 2)
        answer_instance = int(answer_instance)
        group_instance = int(group_instance)
        flat_answers.append({'answer_id': answer_id, 'answer_instance': answer_instance, 'group_instance': group_instance, 'value': v})

    # TODO populate submission data properly
    submission = {
        'submission': {
            'case_id': 'a360486f-c5c9-4e73-9da4-66c5e6a742fd',
            'collection': {
                'exercise_sid': 'f1291d42-1141-4833-aa9b-b6514d9b0210',
                'instrument_id': 'household',
                'period': '201604'
            },
            'data': flat_answers,
            'flushed': False,
            'metadata': {
                'ref_period_end_date': '2016-04-30',
                'ref_period_start_date': '2016-04-01',
                'ru_ref': '123456789012A',
                'user_id': 'integration-test'
            },
            'origin': 'uk.gov.ons.edc.eq',
            'started_at': '2018-10-31T11:44:13.151978+00:00',
            'submitted_at': '2018-10-31T11:44:23.085403+00:00',
            'survey_id': 'census',
            'tx_id': '8330ac0c-ecbb-4f01-8877-b6eac5d0a412',
            'type': 'uk.gov.ons.edc.eq:surveyresponse',
            'version': '0.0.2'
        }
    }

    return web.json_response(submission)


@routes.get('/status')
async def handle_status(request):
    return web.Response(text='ok')


def encrypt_data(key, data):
    jwe_token = jwe.JWE(plaintext=ujson.dumps(data), protected={'alg': 'dir', 'enc': 'A256GCM', 'kid': '1,1'})
    jwe_token.add_recipient(key)
    return jwe_token.serialize(compact=True)


def decrypt_data(key, encrypted_token):
    jwe_token = jwe.JWE(algs=['dir', 'A256GCM'])
    jwe_token.deserialize(encrypted_token, key)
    return ujson.loads(jwe_token.payload.decode())


async def update_answers(request, new_answers):
    storage_key = StorageEncryption._generate_key(request.cookies['user_id'], request.cookies['user_ik'], PEPPER)
    answers = await get_answers(request.cookies['user_id'], storage_key)
    answers.update(new_answers)
    await put_answers(request.cookies['user_id'], answers, storage_key)
    return answers


def ak(answer_id, answer_instance, group_instance):
    return '{}-{}-{}'.format(answer_id, answer_instance, group_instance)


async def parse_date(request, answer_id, group_instance):
    data = await request.post()
    value = '{:04d}-{:02d}-{:02d}'.format(int(data[answer_id + '-year']), int(data[answer_id + '-month']), int(data[answer_id + '-day']))

    return {ak(answer_id, 0, group_instance): value}


async def parse_answers(request, group_instance):
    # TODO csrf

    answers = {}
    data = await request.post()
    for k in data.keys():
        if k != 'csrf_token' and not k.startswith('action'):
            if k in INT_ANSWERS:
                v = int(data.get(k)) if k in data else None
            elif k in LIST_ANSWERS:
                v = data.getall(k)
            else:
                v = data.get(k)

            answers[ak(k, 0, group_instance)] = v

    return answers


def redirect(request, path):
    return web.HTTPFound("http://" + request.host + path)


def render_template(template_name, **kwargs):
    return web.Response(text=env.get_template(template_name).render(kwargs), content_type='text/html')


if __name__ == '__main__':
    app = web.Application()
    app.add_routes(routes)
    app.router.add_static('/static/', 'static')
    web.run_app(app, port=5000)
