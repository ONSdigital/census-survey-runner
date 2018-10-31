import json
from os import listdir

from flask import Flask, render_template, request
from werkzeug.utils import redirect

app = Flask(__name__, template_folder='flat_templates2')
pages = {int(f.split('_')[0]): f for f in listdir('flat_templates2')}
data = []

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


def add_date(key, group_instance):
    value = '{:04d}-{:02d}-{:02d}'.format(int(request.form[key + '-year']), int(request.form[key + '-month']), int(request.form[key + '-day']))
    data.append({'answer_id': key, 'answer_instance': 0, 'group_instance': group_instance, 'value': value})


@app.route('/<int:n>', methods=['GET', 'POST'])
def main(n):
    if request.method == 'POST':
        group_instance = int(pages[n].split('_')[2])

        if n == 7:
            data.append({'answer_id': 'household-relationships-answer', 'answer_instance': 0, 'group_instance': group_instance, 'value': request.form['household-relationships-answer-0']})
        elif n == 23:
            add_date('date-of-birth-answer', group_instance)
        elif n in (65, 71):
            add_date('visitor-date-of-birth-answer', group_instance)
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

                    data.append({'answer_id': k, 'answer_instance': answer_instance, 'group_instance': group_instance, 'value': v})

        return redirect('/' + str(n+1))

    return render_template(pages[n])


@app.route('/session')
def session():
    data.clear()
    return redirect('/0')


@app.route('/dump/submission')
def dump():
    submission = {
        'submission': {
            'case_id': 'a360486f-c5c9-4e73-9da4-66c5e6a742fd',
            'collection': {
                'exercise_sid': 'f1291d42-1141-4833-aa9b-b6514d9b0210',
                'instrument_id': 'household',
                'period': '201604'
            },
            'data': data,
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
