from flask import current_app
from structlog import get_logger

from app.data_model import app_models

logger = get_logger()

TABLE_CONFIG = {
    app_models.SubmittedResponse: {
        'key_field': 'tx_id',
        'schema': app_models.SubmittedResponseSchema,
    },
    app_models.QuestionnaireState: {
        'key_field': 'user_id',
        'schema': app_models.QuestionnaireStateSchema,
    },
    app_models.EQSession: {
        'key_field': 'eq_session_id',
        'schema': app_models.EQSessionSchema,
    },
    app_models.UsedJtiClaim: {
        'key_field': 'jti_claim',
        'schema': app_models.UsedJtiClaimSchema,
    },
}

COLUMN_FAMILY_ID = 'cf1'


def put(model, overwrite):  # pylint: disable=unused-argument
    if not overwrite:
        logger.warning('Only "overwrite" is possible on GCS storage backend')

    instance = get_instance()
    config = TABLE_CONFIG[type(model)]
    schema = config['schema'](strict=True)
    table = instance.table(type(model).__name__)
    key_field = config['key_field']

    row = table.row(getattr(model, key_field))
    item, _ = schema.dump(model)
    for k, v in item.items():
        row.set_cell(COLUMN_FAMILY_ID, k, v)

    row.commit()


def get_by_key(model_type, key_value):
    instance = get_instance()
    config = TABLE_CONFIG[model_type]
    schema = config['schema'](strict=True)
    table = instance.table(model_type.__name__)
    key_field = config['key_field']

    row = table.read_row(key_value.encode('utf-8'))
    if row:
        entity = {k.decode('utf-8'): v[0].value.decode('utf-8') for k, v in row.cells[COLUMN_FAMILY_ID].items()}
        entity[key_field] = key_value
        model, _ = schema.load(entity)
        return model


def delete(model):
    instance = get_instance()
    config = TABLE_CONFIG[type(model)]
    table = instance.table(type(model).__name__)
    key_field = config['key_field']

    table.delete_row(getattr(model, key_field))


def get_instance():
    return current_app.eq['bigtable']
