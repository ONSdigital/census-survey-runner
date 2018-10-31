import json
import os
from decimal import Decimal

from os import listdir

import boto3
import yaml
from botocore.config import Config
from flask import Flask, render_template, request, session
from sdc.crypto.decrypter import decrypt
from sdc.crypto.key_store import KeyStore
from werkzeug.utils import redirect

from app.authentication.user_id_generator import UserIDGenerator
from app.keys import KEY_PURPOSE_AUTHENTICATION
from app.storage.metadata_parser import parse_runner_claims

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

id_generator = UserIDGenerator(10000, secrets['EQ_SERVER_SIDE_STORAGE_USER_ID_SALT'], secrets['EQ_SERVER_SIDE_STORAGE_USER_IK_SALT'])

pages = {int(f.split('_')[0]): f for f in listdir('flat_templates')}

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


def make_date(key, group_instance):
    value = '{:04d}-{:02d}-{:02d}'.format(int(request.form[key + '-year']), int(request.form[key + '-month']), int(request.form[key + '-day']))
    return {'answer_id': key, 'answer_instance': 0, 'group_instance': group_instance, 'value': value}


def put_answers(user_id, answers):
    table = dynamodb.Table(answers_table_name)
    # TODO encrypt
    response = table.put_item(Item={'user_id': user_id, 'answers': answers})['ResponseMetadata']['HTTPStatusCode']
    return response == 200


def json_safe_answer(a):
    if isinstance(a['value'], Decimal):
        a['value'] = int(a['value'])
    a['group_instance'] = int(a['group_instance'])
    a['answer_instance'] = int(a['answer_instance'])
    return a


def get_answers(user_id):
    table = dynamodb.Table(answers_table_name)
    response = table.get_item(Key={'user_id': user_id}, ConsistentRead=True)
    item = response.get('Item')
    return item['answers'] if item else []


@app.route('/<int:n>', methods=['GET', 'POST'])
def main(n):
    answers = get_answers(session['user_id'])

    if request.method == 'POST':
        # TODO csrf

        group_instance = int(pages[n].split('_')[2])

        if n == 7:
            answers.append({'answer_id': 'household-relationships-answer', 'answer_instance': 0, 'group_instance': group_instance, 'value': request.form['household-relationships-answer-0']})
        elif n == 23:
            answers.append(make_date('date-of-birth-answer', group_instance))
        elif n in (65, 71):
            answers.append(make_date('visitor-date-of-birth-answer', group_instance))
        else:
            for k, v in request.form.items():
                if k != 'csrf_token' and not k.startswith('action'):

                    answer_instance = 0
                    if n == 4:
                        ns, answer_instance, k = k.split('-', 2)
                        assert ns == 'household'
                        answer_instance = int(answer_instance)

                    if k in int_answers:
                        v = int(v)
                    elif k in list_answers:
                        v = request.form.getlist(k)

                    answers.append({'answer_id': k, 'answer_instance': answer_instance, 'group_instance': group_instance, 'value': v})

        put_answers(session['user_id'], answers)

        # TODO routing based on answers
        return redirect('/' + str(n+1))

    # TODO add in existing form data
    # TODO add in variables e.g. household member name
    return render_template(pages[n])


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

    return redirect('/0')


@app.route('/dump/submission')
def dump():
    answers = get_answers(session['user_id'])
    answers = [json_safe_answer(a) for a in answers]

    # TODO populate submission data properly
    submission = {
        'submission': {
            'case_id': 'a360486f-c5c9-4e73-9da4-66c5e6a742fd',
            'collection': {
                'exercise_sid': 'f1291d42-1141-4833-aa9b-b6514d9b0210',
                'instrument_id': 'household',
                'period': '201604'
            },
            'data': answers,
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
