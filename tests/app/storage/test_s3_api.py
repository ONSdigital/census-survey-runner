import io
import json

import mock
from botocore.exceptions import ClientError
from tests.app.app_context_test_case import AppContextTestCase

from app.data_model.app_models import QuestionnaireState, QuestionnaireStateSchema
from app.storage import s3_api


class TestS3Api(AppContextTestCase):

    def setUp(self):
        super().setUp()

        self.mock_client = mock.MagicMock()
        self._app.eq['s3'] = self.mock_client

    def test_get_by_key(self):
        model = QuestionnaireState('someuser', 'data', 1)
        model_data, _ = QuestionnaireStateSchema(strict=True).dump(model)

        self.mock_client.get_object.return_value = {
            'Body': io.StringIO(json.dumps(model_data))
        }

        returned_model = s3_api.get_by_key(QuestionnaireState, 'someuser')

        self.mock_client.get_object.assert_called_once_with(
            Bucket=self._app.config['EQ_QUESTIONNAIRE_STATE_TABLE_NAME'],
            Key=model.user_id
        )

        self.assertEqual(model.user_id, returned_model.user_id)
        self.assertEqual(model.state_data, returned_model.state_data)
        self.assertEqual(model.version, returned_model.version)

    def test_get_no_such_key(self):
        self.mock_client.get_object.side_effect = ClientError({
            'Error': {'Code': 'NoSuchKey'}
        }, 'get_object')

        returned_model = s3_api.get_by_key(QuestionnaireState, 'someuser')
        self.assertFalse(returned_model)

    def test_put(self):
        model = QuestionnaireState('someuser', 'data', 1)

        s3_api.put(model, True)

        self.assertEqual(
            self.mock_client.put_object.call_args[1]['Key'],
            model.user_id
        )

        data = self.mock_client.put_object.call_args[1]['Body']
        put_data = json.loads(data)

        self.assertEqual(model.user_id, put_data['user_id'])
        self.assertEqual(model.state_data, put_data['state_data'])
        self.assertEqual(str(model.version), put_data['version'])

    def test_delete(self):
        model = QuestionnaireState('someuser', 'data', 1)
        s3_api.delete(model)

        self.mock_client.delete_object.assert_called_once_with(
            Bucket=self._app.config['EQ_QUESTIONNAIRE_STATE_TABLE_NAME'],
            Key=model.user_id
        )
