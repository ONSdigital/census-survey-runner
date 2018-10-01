import json

import mock
from google.cloud.exceptions import NotFound
from tests.app.app_context_test_case import AppContextTestCase

from app.data_model.app_models import QuestionnaireState, QuestionnaireStateSchema
from app.storage import gcs_api


class TestGCSApi(AppContextTestCase):

    def setUp(self):
        super().setUp()

        self.mock_bucket = mock.Mock()
        self._app.eq['gcsbucket'] = self.mock_bucket

    def test_get_by_key(self):
        m_blob = mock.Mock()
        self.mock_bucket.blob.return_value = m_blob

        model = QuestionnaireState('someuser', 'data', 1)
        model_data, _ = QuestionnaireStateSchema(strict=True).dump(model)
        m_blob.download_as_string.return_value = json.dumps(model_data)

        returned_model = gcs_api.get_by_key(QuestionnaireState, 'someuser')

        self.assertEqual(model.user_id, returned_model.user_id)
        self.assertEqual(model.state_data, returned_model.state_data)
        self.assertEqual(model.version, returned_model.version)

    def test_get_not_found(self):
        m_blob = self.mock_bucket.blob.return_value
        m_blob.download_as_string.side_effect = NotFound('foo')

        returned_model = gcs_api.get_by_key(QuestionnaireState, 'someuser')
        self.assertFalse(returned_model)

    def test_put(self):
        m_blob = mock.Mock()
        self.mock_bucket.blob.return_value = m_blob

        model = QuestionnaireState('someuser', 'data', 1)

        gcs_api.put(model, False)

        put_data = json.loads(m_blob.upload_from_string.call_args[0][0])

        self.assertEqual(model.user_id, put_data['user_id'])
        self.assertEqual(model.state_data, put_data['state_data'])
        self.assertEqual(str(model.version), put_data['version'])

    def test_delete(self):
        m_blob = mock.Mock()
        self.mock_bucket.blob.return_value = m_blob

        model = QuestionnaireState('someuser', 'data', 1)
        gcs_api.delete(model)

        key = '{}/someuser'.format(
            self._app.config['EQ_QUESTIONNAIRE_STATE_TABLE_NAME']
        )
        self.mock_bucket.blob.assert_called_once_with(key)
        m_blob.delete.assert_called_once()
