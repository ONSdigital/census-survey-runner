import unittest
import warnings

from flask import current_app

from app import flask_theme_cache
from app.setup import create_app
from app.utilities import schema as schema_utils
from app.storage.dynamodb_api import TABLE_CONFIG

with warnings.catch_warnings():
    warnings.filterwarnings('ignore', category=DeprecationWarning)
    from moto import mock_dynamodb2



class AppContextTestCase(unittest.TestCase):
    """
    unittest.TestCase that creates a Flask app context on setUp
    and destroys it on tearDown
    """
    LOGIN_DISABLED = False
    setting_overrides = {}

    def setUp(self):
        self._ddb = mock_dynamodb2()
        self._ddb.start()

        setting_overrides = {
            'SQLALCHEMY_DATABASE_URI': 'sqlite://',
            'LOGIN_DISABLED': self.LOGIN_DISABLED,
            'EQ_DYNAMODB_ENDPOINT': None,
        }
        setting_overrides.update(self.setting_overrides)
        self._app = create_app(setting_overrides)

        self._app.config['SERVER_NAME'] = 'test.localdomain'
        self._app_context = self._app.app_context()
        self._app_context.push()

        setup_tables()

    def tearDown(self):
        self._app_context.pop()

        self._ddb.stop()

        flask_theme_cache.clear()
        schema_utils.clear_schema_cache()

    def app_request_context(self, *args, **kwargs):
        return self._app.test_request_context(*args, **kwargs)


def setup_tables():
    if current_app.config['EQ_STORAGE_BACKEND'] == 'dynamodb':
        for config in TABLE_CONFIG.values():
            table_name = current_app.config[config['table_name_key']]
            current_app.eq['dynamodb'].create_table(
                TableName=table_name,
                AttributeDefinitions=[{'AttributeName': config['key_field'], 'AttributeType': 'S'}],
                KeySchema=[{'AttributeName': config['key_field'], 'KeyType': 'HASH'}],
                ProvisionedThroughput={'ReadCapacityUnits': 1, 'WriteCapacityUnits': 1}
            )
