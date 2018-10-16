import json

import mock
from tests.app.app_context_test_case import AppContextTestCase

from app.data_model.app_models import QuestionnaireState, QuestionnaireStateSchema
from app.storage import redis_api


class TestRedisApi(AppContextTestCase):

    def setUp(self):
        super().setUp()

        self.mock_redis = mock.MagicMock()
        self._app.eq['redis'] = {
            redis_api.TABLE_CONFIG[QuestionnaireState]['db_index']: self.mock_redis
        }

    def test_get_by_key(self):
        model = QuestionnaireState('someuser', 'data', 1)
        model_data, _ = QuestionnaireStateSchema(strict=True).dump(model)

        self.mock_redis.get.return_value = json.dumps(model_data)

        returned_model = redis_api.get_by_key(QuestionnaireState, 'someuser')

        self.assertEqual(model.user_id, returned_model.user_id)
        self.assertEqual(model.state_data, returned_model.state_data)
        self.assertEqual(model.version, returned_model.version)

    def test_put(self):
        model = QuestionnaireState('someuser', 'data', 1)

        redis_api.put(model, True)

        key, data = self.mock_redis.set.call_args[0]
        put_data = json.loads(data)

        self.assertEqual(key, model.user_id)

        self.assertEqual(model.user_id, put_data['user_id'])
        self.assertEqual(model.state_data, put_data['state_data'])
        self.assertEqual(str(model.version), put_data['version'])

    def test_put_overwrite(self):
        model = QuestionnaireState('someuser', 'data', 1)

        redis_api.put(model, False)

        key, data = self.mock_redis.setnx.call_args[0]
        put_data = json.loads(data)

        self.assertEqual(key, model.user_id)

        self.assertEqual(model.user_id, put_data['user_id'])
        self.assertEqual(model.state_data, put_data['state_data'])
        self.assertEqual(str(model.version), put_data['version'])

    def test_delete(self):
        model = QuestionnaireState('someuser', 'data', 1)
        redis_api.delete(model)

        self.mock_redis.delete.assert_called_once_with(model.user_id)
