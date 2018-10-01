from flask import current_app
from google.cloud.exceptions import NotFound

from structlog import get_logger
import ujson
from app.data_model import app_models

logger = get_logger()


TABLE_CONFIG = {
    app_models.SubmittedResponse: {
        'key_field': 'tx_id',
        'table_name_key': 'EQ_SUBMITTED_RESPONSES_TABLE_NAME',
        'schema': app_models.SubmittedResponseSchema,
    },
    app_models.QuestionnaireState: {
        'key_field': 'user_id',
        'table_name_key': 'EQ_QUESTIONNAIRE_STATE_TABLE_NAME',
        'schema': app_models.QuestionnaireStateSchema,
    },
    app_models.EQSession: {
        'key_field': 'eq_session_id',
        'table_name_key': 'EQ_SESSION_TABLE_NAME',
        'schema': app_models.EQSessionSchema,
    },
    app_models.UsedJtiClaim: {
        'key_field': 'jti_claim',
        'table_name_key': 'EQ_USED_JTI_CLAIM_TABLE_NAME',
        'schema': app_models.UsedJtiClaimSchema,
    },
}


def put(model, overwrite):  # pylint: disable=unused-argument
    if not overwrite:
        logger.warning('Only "overwrite" is possible on GCS storage backend')  # pragma: no cover

    config = TABLE_CONFIG[type(model)]
    schema = config['schema'](strict=True)
    key = getattr(model, config['key_field'])
    gcs_key = make_key(config, key)

    item, _ = schema.dump(model)
    blob = get_bucket().blob(gcs_key)
    blob.upload_from_string(ujson.dumps(item))  # pylint: disable=c-extension-no-member


def get_by_key(model_type, key_value):
    config = TABLE_CONFIG[model_type]
    schema = config['schema'](strict=True)

    gcs_key = make_key(config, key_value)
    blob = get_bucket().blob(gcs_key)

    try:
        data = blob.download_as_string()
    except NotFound:
        data = None

    if data:
        model, _ = schema.load(ujson.loads(data))  # pylint: disable=c-extension-no-member
        return model


def delete(model):
    config = TABLE_CONFIG[type(model)]
    key = getattr(model, config['key_field'])
    gcs_key = make_key(config, key)

    blob = get_bucket().blob(gcs_key)
    blob.delete()


def make_key(config, key_value):
    table_name = current_app.config[config['table_name_key']]
    return '{}/{}'.format(table_name, key_value)


def get_bucket():
    return current_app.eq['gcsbucket']
