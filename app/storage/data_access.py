from flask import current_app

from app.storage import (
    dynamodb_api,
    sql_api,
    bigtable_api,
    s3_api,
    redis_api,
    gcs_api,
    gc_datastore_api,
)

STORAGE_BACKENDS = {
    'dynamodb': dynamodb_api,
    's3': s3_api,
    'sql': sql_api,
    'bigtable': bigtable_api,
    'redis': redis_api,
    'gcs': gcs_api,
    'gc_datastore': gc_datastore_api,
}


def get_by_key(model_type, key_value):
    """Gets a given model by its key

    :param model: the type of the app model to fetch
    :param key_value: the value of the model's key
    """
    return _get_backend().get_by_key(model_type, key_value)


def put(model, overwrite=True):
    """Inserts or updates the given app model

    :param model: the app model to be saved
    :param overwrite: if true then the object may overwrite an existing object
        with the same ID. if not a `ItemAlreadyExistsError` will be raised
    """
    _get_backend().put(model, overwrite)


def delete(model):
    """Deletes the given app model

    :param model: the app model to be deleted
    """
    _get_backend().delete(model)


def _get_backend():
    return STORAGE_BACKENDS[current_app.config['EQ_STORAGE_BACKEND']]
