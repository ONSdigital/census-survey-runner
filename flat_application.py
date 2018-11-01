import os
import ujson
from uuid import uuid4

import boto3
import yaml
from botocore.config import Config
from flask import Flask, render_template, request, session
from google.cloud import storage
from google.cloud.exceptions import NotFound
from jwcrypto import jwe
from sdc.crypto.decrypter import decrypt
from sdc.crypto.key_store import KeyStore
from werkzeug.utils import redirect

from app.authentication.user_id_generator import UserIDGenerator
from app.keys import KEY_PURPOSE_AUTHENTICATION
from app.storage.metadata_parser import parse_runner_claims
from app.storage.storage_encryption import StorageEncryption

storage_backend = os.getenv('EQ_STORAGE_BACKEND')
if storage_backend == 'gcs':
    client = storage.Client()
    gcs_bucket = client.get_bucket(os.getenv('EQ_GCS_BUCKET_ID'))

    def get_answers(user_id, key):
        try:
            blob = gcs_bucket.blob('{}/{}'.format('flat', user_id))
            return decrypt_data(key, blob.download_as_string().decode())
        except NotFound:
            return {}

    def put_answers(user_id, answers, key):
        blob = gcs_bucket.blob('{}/{}'.format('flat', user_id))
        blob.upload_from_string(encrypt_data(key, answers))
else:
    dynamodb = boto3.resource('dynamodb', endpoint_url=os.getenv('EQ_DYNAMODB_ENDPOINT'), config=Config(
        retries={'max_attempts': int(os.getenv('EQ_DYNAMODB_MAX_RETRIES', '5'))},
        max_pool_connections=int(os.getenv('EQ_DYNAMODB_MAX_POOL_CONNECTIONS', '30')),
    ))
    dynamodb_table_name = os.getenv('EQ_QUESTIONNAIRE_STATE_TABLE_NAME', 'dev-questionnaire-state')

    def get_answers(user_id, key):
        table = dynamodb.Table(dynamodb_table_name)
        response = table.get_item(Key={'user_id': user_id}, ConsistentRead=True)
        item = response.get('Item')
        return decrypt_data(key, item['answers']) if item else {}

    def put_answers(user_id, answers, key):
        table = dynamodb.Table(dynamodb_table_name)
        table.put_item(Item={'user_id': user_id, 'answers': encrypt_data(key, answers)})

with open(os.getenv('EQ_KEYS_FILE', 'keys.yml')) as f:
    key_store = KeyStore(yaml.safe_load(f))

with open(os.getenv('EQ_SECRETS_FILE', 'secrets.yml')) as secrets_file:
    secrets = yaml.safe_load(secrets_file)['secrets']

app = Flask(__name__, template_folder='flat_templates')
app.secret_key = secrets['EQ_SECRET_KEY']

id_generator = UserIDGenerator(10000, secrets['EQ_SERVER_SIDE_STORAGE_USER_ID_SALT'], secrets['EQ_SERVER_SIDE_STORAGE_USER_IK_SALT'])

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


@app.route('/session')
def create_session():
    if session:
        session.clear()

    decrypted_token = decrypt(token=request.args.get('token'), key_store=key_store, key_purpose=KEY_PURPOSE_AUTHENTICATION, leeway=120)

    # TODO validate JTI

    claims = parse_runner_claims(decrypted_token)

    user_id = id_generator.generate_id(claims)
    user_ik = id_generator.generate_ik(claims)

    session['user_id'] = user_id
    session['user_ik'] = user_ik

    return redirect('/introduction')


@app.route('/fake_session')
def create_fake_session():
    if session:
        session.clear()

    session['user_id'] = str(uuid4())
    session['user_ik'] = str(uuid4())

    return redirect('/introduction')


@app.route('/introduction', methods=['GET', 'POST'])
def handle_introduction():
    if request.method == 'POST':
        answers = parse_answers(0)
        update_answers(answers)
        return redirect('/address')

    return render_template('introduction.html')


@app.route('/address', methods=['GET', 'POST'])
def handle_address():
    if request.method == 'POST':
        answers = parse_answers(0)
        update_answers(answers)
        return redirect('/members/introduction')

    return render_template('address.html')


@app.route('/members/<page>', methods=['GET', 'POST'])
def handle_members(page):
    if request.method == 'POST':
        if page == 'household-composition':
            answers = {}
            for k, v in request.form.items():
                if k.startswith('household-'):
                    _, answer_instance, k = k.split('-', 2)
                    answer_instance = int(answer_instance)
                    answers[ak(k, answer_instance, 0)] = v
        elif page == 'household-relationships':
            answers = {}
            for k, v in request.form.items():
                if k.startswith('household-relationships-answer-'):
                    _, answer_instance = k.rsplit('-', 1)
                    answer_instance = int(answer_instance)
                    answers[ak('household-relationships-answer', answer_instance, 0)] = v
        else:
            answers = parse_answers(0)

        update_answers(answers)
        i = MEMBERS_PAGES.index(page) + 1
        return redirect('/household/introduction' if i >= len(MEMBERS_PAGES) else '/members/{}'.format(MEMBERS_PAGES[i]))

    storage_key = StorageEncryption._generate_key(session['user_id'], session['user_ik'], PEPPER)
    answers = get_answers(session['user_id'], storage_key)

    first_names = [v for (k, v) in answers.items() if k.startswith('first-name-')]
    middle_names = [v for (k, v) in answers.items() if k.startswith('middle-names-')]
    last_names = [v for (k, v) in answers.items() if k.startswith('last-name-')]
    members = [' '.join(n) for n in zip(first_names, middle_names, last_names)]

    address_line_1 = answers[ak('address-line-1', 0, 0)]

    return render_template('members/{}.html'.format(page), members=members, address_line_1=address_line_1)


@app.route('/household/<page>', methods=['GET', 'POST'])
def handle_household(page):
    if request.method == 'POST':
        answers = parse_answers(0)
        update_answers(answers)
        i = HOUSEHOLD_PAGES.index(page) + 1
        return redirect('/member/0/introduction' if i >= len(HOUSEHOLD_PAGES) else '/household/{}'.format(HOUSEHOLD_PAGES[i]))

    return render_template('household/{}.html'.format(page))


@app.route('/member/<int:group_instance>/<page>', methods=['GET', 'POST'])
def handle_member(group_instance, page):
    if request.method == 'POST':
        if page == 'date-of-birth':
            answers = parse_date('date-of-birth-answer', group_instance)
        else:
            answers = parse_answers(group_instance)

        answers = update_answers(answers)

        if page == 'private-response':
            if request.form['private-response-answer'].startswith('Yes'):
                return redirect('/member/{}/request-private-response'.format(group_instance))

        if page == 'request-private-response':
            return redirect('/member/{}/completed'.format(group_instance))

        i = MEMBER_PAGES.index(page) + 1
        if i < len(MEMBER_PAGES):
            return redirect('/member/{}/{}'.format(group_instance, MEMBER_PAGES[i]))

        num_members = len([a for a in answers.keys() if a.startswith('first-name-')])

        group_instance += 1

        return redirect('/visitors_introduction' if group_instance >= num_members else '/member/{}/introduction'.format(group_instance))

    storage_key = StorageEncryption._generate_key(session['user_id'], session['user_ik'], PEPPER)
    answers = get_answers(session['user_id'], storage_key)

    first_name = answers[ak('first-name', group_instance, 0)]
    middle_names = answers[ak('middle-names', group_instance, 0)]
    last_name = answers[ak('last-name', group_instance, 0)]

    return render_template('member/{}.html'.format(page), first_name=first_name, middle_names=middle_names, last_name=last_name)


@app.route('/visitors_introduction', methods=['GET', 'POST'])
def handle_visitors_introduction():
    if request.method == 'POST':
        answers = parse_answers(0)
        update_answers(answers)
        return redirect('/visitor/0/name')

    return render_template('visitors_introduction.html')


@app.route('/visitor/<int:group_instance>/<page>', methods=['GET', 'POST'])
def handle_visitor(group_instance, page):
    if request.method == 'POST':
        if page == 'date-of-birth':
            answers = parse_date('visitor-date-of-birth-answer', group_instance)
        else:
            answers = parse_answers(group_instance)

        answers = update_answers(answers)

        i = VISITOR_PAGES.index(page) + 1
        if i < len(VISITOR_PAGES):
            return redirect('/visitor/{}/{}'.format(group_instance, VISITOR_PAGES[i]))

        num_visitors = answers[ak('overnight-visitors-answer', 0, 0)]

        group_instance += 1

        return redirect('/visitors_completed' if group_instance >= num_visitors else '/visitor/{}/name'.format(group_instance))

    return render_template('visitor/{}.html'.format(page), group_instance=group_instance)


@app.route('/visitors_completed', methods=['GET', 'POST'])
def handle_visitors_completed():
    if request.method == 'POST':
        answers = parse_answers(0)
        update_answers(answers)
        return redirect('/completed')

    return render_template('visitors_completed.html')


@app.route('/completed', methods=['GET', 'POST'])
def handle_completed():
    if request.method == 'POST':
        print('Submitting', get_submission())
        # TODO validate and submit answers
        return redirect('/thank-you')

    return render_template('completed.html')


@app.route('/thank-you')
def handle_thank_you():
    return render_template('thank-you.html')


@app.route('/dump/submission')
def get_submission():
    storage_key = StorageEncryption._generate_key(session['user_id'], session['user_ik'], PEPPER)
    answers = get_answers(session['user_id'], storage_key)

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

    return ujson.dumps(submission)


def encrypt_data(key, data):
    jwe_token = jwe.JWE(plaintext=ujson.dumps(data), protected={'alg': 'dir', 'enc': 'A256GCM', 'kid': '1,1'})
    jwe_token.add_recipient(key)
    return jwe_token.serialize(compact=True)


def decrypt_data(key, encrypted_token):
    jwe_token = jwe.JWE(algs=['dir', 'A256GCM'])
    jwe_token.deserialize(encrypted_token, key)
    return ujson.loads(jwe_token.payload.decode())


def update_answers(new_answers):
    storage_key = StorageEncryption._generate_key(session['user_id'], session['user_ik'], PEPPER)
    answers = get_answers(session['user_id'], storage_key)
    answers.update(new_answers)
    put_answers(session['user_id'], answers, storage_key)
    return answers


def ak(answer_id, answer_instance, group_instance):
    return '{}-{}-{}'.format(answer_id, answer_instance, group_instance)


def parse_date(answer_id, group_instance):
    value = '{:04d}-{:02d}-{:02d}'.format(int(request.form[answer_id + '-year']), int(request.form[answer_id + '-month']), int(request.form[answer_id + '-day']))

    return {ak(answer_id, 0, group_instance): value}


def parse_answers(group_instance):
    # TODO csrf

    answers = {}
    for k, v in request.form.items():
        if k != 'csrf_token' and not k.startswith('action'):
            if k in INT_ANSWERS:
                v = int(v) if v else None
            elif k in LIST_ANSWERS:
                v = request.form.getlist(k)

            answers[ak(k, 0, group_instance)] = v

    return answers


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001)
