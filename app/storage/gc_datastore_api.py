from flask import current_app
from google.cloud import datastore
from structlog import get_logger

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
        logger.warning('Only "overwrite" is currently supported on cloud datastore storage backend')

    client = get_client()
    config = TABLE_CONFIG[type(model)]

    schema = config['schema'](strict=True)
    item, _ = schema.dump(model)

    key_value = getattr(model, config['key_field'])
    table_name = current_app.config[config['table_name_key']]
    key = client.key(table_name, key_value)

    entity = datastore.Entity(key=key, exclude_from_indexes=list(item.keys()))
    entity.update(item)
    client.put(entity)


def get_by_key(model_type, key_value):
    client = get_client()
    config = TABLE_CONFIG[model_type]

    table_name = current_app.config[config['table_name_key']]
    key = client.key(table_name, key_value)

    schema = config['schema'](strict=True)

    item = client.get(key)
    if item:
        model, _ = schema.load(item)
        return model


def delete(model):
    client = get_client()
    config = TABLE_CONFIG[type(model)]

    key_value = getattr(model, config['key_field'])
    table_name = current_app.config[config['table_name_key']]
    key = client.key(table_name, key_value)

    return client.delete(key)


def get_client():
    return current_app.eq['gc_datastore']
