import json
import os
from decimal import Decimal

from os import listdir
from uuid import uuid4

import boto3
import yaml
from botocore.config import Config
from flask import Flask, render_template, request, session
from jwcrypto import jwe
from sdc.crypto.decrypter import decrypt
from sdc.crypto.key_store import KeyStore
from werkzeug.utils import redirect

from app.authentication.user_id_generator import UserIDGenerator
from app.keys import KEY_PURPOSE_AUTHENTICATION
from app.storage.metadata_parser import parse_runner_claims
from app.storage.storage_encryption import StorageEncryption

app = Flask(__name__, template_folder='flat_templates')

config = Config(
    retries={'max_attempts': int(os.getenv('EQ_DYNAMODB_MAX_RETRIES', '5'))},
    max_pool_connections=int(os.getenv('EQ_DYNAMODB_MAX_POOL_CONNECTIONS', '30')),
)

dynamodb = boto3.resource('dynamodb', endpoint_url=os.getenv('EQ_DYNAMODB_ENDPOINT'), config=config)

answers_table_name = os.getenv('EQ_QUESTIONNAIRE_STATE_TABLE_NAME', 'dev-questionnaire-state')

with open(os.getenv('EQ_KEYS_FILE', 'keys.yml')) as f:
    key_store = KeyStore(yaml.safe_load(f))

with open(os.getenv('EQ_SECRETS_FILE', 'secrets.yml')) as secrets_file:
    secrets = yaml.safe_load(secrets_file)['secrets']

app.secret_key = secrets['EQ_SECRET_KEY']

pepper = secrets['EQ_SERVER_SIDE_STORAGE_ENCRYPTION_USER_PEPPER']

id_generator = UserIDGenerator(10000, secrets['EQ_SERVER_SIDE_STORAGE_USER_ID_SALT'], secrets['EQ_SERVER_SIDE_STORAGE_USER_IK_SALT'])

int_answers = {
    'overnight-visitors-answer',
    'number-of-bedrooms-answer',
    'number-of-vehicles-answer'
}

list_answers = {
    'central-heating-answer',
    'national-identity-england-answer',
    'religion-answer',
    'passports-answer',
    'qualifications-england-answer',
    'employment-type-answer',
    'occupation-answer'
}


def key(answer_id, answer_instance, group_instance):
    return answer_id + '-' + str(answer_instance) + '-' + str(group_instance)


def make_date(answer_id, group_instance):
    value = '{:04d}-{:02d}-{:02d}'.format(int(request.form[answer_id + '-year']), int(request.form[answer_id + '-month']), int(request.form[answer_id + '-day']))

    return {key(answer_id, 0, group_instance): value}


def encrypt_data(key, data):
    jwe_token = jwe.JWE(plaintext=json.dumps(data), protected={'alg': 'dir', 'enc': 'A256GCM', 'kid': '1,1'})
    jwe_token.add_recipient(key)
    return jwe_token.serialize(compact=True)


def decrypt_data(key, encrypted_token):
    jwe_token = jwe.JWE(algs=['dir', 'A256GCM'])
    jwe_token.deserialize(encrypted_token, key)
    return json.loads(jwe_token.payload.decode())


def put_answers(user_id, answers, key):
    table = dynamodb.Table(answers_table_name)
    response = table.put_item(Item={'user_id': user_id, 'answers': encrypt_data(key, answers)})['ResponseMetadata']['HTTPStatusCode']
    return response == 200


def get_answers(user_id, key):
    table = dynamodb.Table(answers_table_name)
    response = table.get_item(Key={'user_id': user_id}, ConsistentRead=True)
    item = response.get('Item')
    return decrypt_data(key, item['answers']) if item else {}


def json_safe_answer(a):
    if isinstance(a['value'], Decimal):
        a['value'] = int(a['value'])
    a['group_instance'] = int(a['group_instance'])
    a['answer_instance'] = int(a['answer_instance'])
    return a


def handle_post(group_instance, new_answers=None):
    # TODO csrf

    storage_key = StorageEncryption._generate_key(session['user_id'], session['user_ik'], pepper)
    answers = get_answers(session['user_id'], storage_key)

    if new_answers is not None:
        answers.update(new_answers)
    else:
        for k, v in request.form.items():
            if k != 'csrf_token' and not k.startswith('action'):
                if k in int_answers:
                    v = int(v) if v else None
                elif k in list_answers:
                    v = request.form.getlist(k)

                answers[key(k, 0, group_instance)] = v

    put_answers(session['user_id'], answers, storage_key)

    return answers


members_pages = [
    'introduction',
    'permanent-or-family-home',
    'household-composition',
    'everyone-at-address-confirmation',
    'overnight-visitors',
    'household-relationships',
    'completed'
]

household_pages = [
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

member_pages = [
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

visitor_pages = [
    'name',
    'sex',
    'date-of-birth',
    'uk-resident',
    'address',
    'completed'
]


@app.route('/introduction', methods=['GET', 'POST'])
def handle_introduction():
    if request.method == 'POST':
        handle_post(0)
        return redirect('/address')

    return render_template('introduction.html')


@app.route('/address', methods=['GET', 'POST'])
def handle_address():
    if request.method == 'POST':
        handle_post(0)
        return redirect('/members/introduction')

    return render_template('address.html')


@app.route('/members/<page>', methods=['GET', 'POST'])
def handle_members(page):
    if request.method == 'POST':
        answers = None
        if page == 'household-composition':
            answers = {}
            for k, v in request.form.items():
                if k.startswith('household-'):
                    _, answer_instance, k = k.split('-', 2)
                    answer_instance = int(answer_instance)
                    answers[key(k, answer_instance, 0)] = v
        if page == 'household-relationships':
            # TODO decode whole matrix
            answers = {key('household-relationships-answer', 0, 0):  request.form['household-relationships-answer-0']}

        handle_post(0, new_answers=answers)
        i = members_pages.index(page) + 1
        return redirect('/household/introduction' if i >= len(members_pages) else '/members/' + members_pages[i])

    return render_template('members/' + page + '.html')


@app.route('/household/<page>', methods=['GET', 'POST'])
def handle_household(page):
    if request.method == 'POST':
        handle_post(0)
        i = household_pages.index(page) + 1
        return redirect('/member/0/introduction' if i >= len(household_pages) else '/household/' + household_pages[i])

    return render_template('household/' + page + '.html')


@app.route('/member/<int:group_instance>/<page>', methods=['GET', 'POST'])
def handle_member(group_instance, page):
    if request.method == 'POST':
        answers = None
        if page == 'date-of-birth':
            answers = make_date('date-of-birth-answer', group_instance)

        answers = handle_post(group_instance, new_answers=answers)

        if page == 'private-response':
            if request.form['private-response-answer'].startswith('Yes'):
                return redirect('/member/' + str(group_instance) + '/request-private-response')

        if page == 'request-private-response':
            return redirect('/member/' + str(group_instance) + '/completed')

        i = member_pages.index(page) + 1
        if i < len(member_pages):
            return redirect('/member/' + str(group_instance) + '/' + member_pages[i])

        num_members = len([a for a in answers.keys() if a.startswith('first-name')])

        group_instance = int(group_instance) + 1

        return redirect('/visitors_introduction' if group_instance >= num_members else '/member/' + str(group_instance) + '/introduction')

    storage_key = StorageEncryption._generate_key(session['user_id'], session['user_ik'], pepper)
    answers = get_answers(session['user_id'], storage_key)

    first_name = answers[key('first-name', group_instance, 0)]
    last_name = answers[key('last-name', group_instance, 0)]

    return render_template('member/' + page + '.html', first_name=first_name, last_name=last_name)


@app.route('/visitors_introduction', methods=['GET', 'POST'])
def handle_visitors_introduction():
    if request.method == 'POST':
        handle_post(0)
        return redirect('/visitor/0/name')

    return render_template('visitors_introduction.html')


@app.route('/visitor/<int:group_instance>/<page>', methods=['GET', 'POST'])
def handle_visitor(group_instance, page):
    if request.method == 'POST':
        answers = None
        if page == 'date-of-birth':
            answers = make_date('visitor-date-of-birth-answer', group_instance)

        answers = handle_post(group_instance, new_answers=answers)

        i = visitor_pages.index(page) + 1
        if i < len(visitor_pages):
            return redirect('/visitor/' + str(group_instance) + '/' + visitor_pages[i])

        num_visitors = answers[key('overnight-visitors-answer', 0, 0)]

        group_instance = int(group_instance) + 1

        return redirect('/visitors_completed' if group_instance >= num_visitors else '/visitor/' + str(group_instance) + '/name')

    return render_template('visitor/' + page + '.html', group_instance=group_instance)


@app.route('/visitors_completed', methods=['GET', 'POST'])
def handle_visitors_completed():
    if request.method == 'POST':
        handle_post(0)
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


@app.route('/dump/submission')
def get_submission():
    storage_key = StorageEncryption._generate_key(session['user_id'], session['user_ik'], pepper)
    answers = get_answers(session['user_id'], storage_key)

    flat_answers = []

    for k, v in answers.items():
        answer_id, answer_instance, group_instance = k.rsplit('-', 2)
        answer_instance = int(answer_instance)
        group_instance = int(group_instance)
        if isinstance(v, Decimal):
            v = int(v)
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

    return json.dumps(submission)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001)
