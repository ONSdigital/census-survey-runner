import mock
from tests.app.app_context_test_case import AppContextTestCase

from app.data_model.app_models import QuestionnaireState, QuestionnaireStateSchema
from app.storage import bigtable_api


class TestBigTableApi(AppContextTestCase):

    def setUp(self):
        super().setUp()

        self.mock_instance = mock.MagicMock()
        self._app.eq['bigtable'] = self.mock_instance

    def test_get_by_key(self):
        model = QuestionnaireState('someuser', 'data', 1)
        model_data, _ = QuestionnaireStateSchema(strict=True).dump(model)

        read_row = self.mock_instance.table.return_value.read_row
        read_row.return_value.cells = {'cf1': {
            k.encode(): [mock.Mock(value=v.encode())] for k, v in model_data.items()
        }}

        returned_model = bigtable_api.get_by_key(QuestionnaireState, 'someuser')

        read_row.assert_called_once_with(b'someuser')

        self.assertEqual(model.user_id, returned_model.user_id)
        self.assertEqual(model.state_data, returned_model.state_data)
        self.assertEqual(model.version, returned_model.version)

    def test_put(self):
        model = QuestionnaireState('someuser', 'data', 1)

        row = self.mock_instance.table.return_value.row
        set_cell = row.return_value.set_cell

        bigtable_api.put(model, False)

        cell_calls = set_cell.call_args_list

        self.assertIn(mock.call('cf1', 'user_id', model.user_id), cell_calls)
        self.assertIn(mock.call('cf1', 'state_data', model.state_data), cell_calls)
        self.assertIn(mock.call('cf1', 'version', str(model.version)), cell_calls)

        row.return_value.commit.assert_called_once()

    def test_delete(self):
        model = QuestionnaireState('someuser', 'data', 1)
        bigtable_api.delete(model)

        delete_row = self.mock_instance.table.return_value.delete_row
        delete_row.assert_called_once_with('someuser')
