from tests.app.app_context_test_case import AppContextTestCase

from app.data_model import app_models, models
from app.storage import sql_api
from app.storage.errors import ItemAlreadyExistsError


class TestSQLApi(AppContextTestCase):
    setting_overrides = {'EQ_STORAGE_BACKEND': 'sql'}

    def test_get_by_key(self):
        sql_model = _save_dummy_object()

        returned_model = sql_api.get_by_key(app_models.QuestionnaireState, 'someuser')

        self.assertIsInstance(returned_model, app_models.QuestionnaireState)
        self.assertEqual(returned_model.user_id, sql_model.user_id)
        self.assertEqual(returned_model.state_data, sql_model.state)
        self.assertEqual(returned_model.version, sql_model.version)

    def test_put(self):
        app_model = app_models.QuestionnaireState('someuser', 'data', 1)

        sql_api.put(app_model, False)

        sql_model = (
            models.QuestionnaireState
            .query
            .filter_by(user_id='someuser')
            .first()
        )

        self.assertEqual(app_model.user_id, sql_model.user_id)
        self.assertEqual(app_model.state_data, sql_model.state)
        self.assertEqual(app_model.version, sql_model.version)

    def test_put_conflict(self):
        existing_sql_model = _save_dummy_object()
        app_model = existing_sql_model.to_app_model()

        with self.assertRaises(ItemAlreadyExistsError):
            sql_api.put(app_model, False)

    def test_put_overwrite(self):
        existing_sql_model = _save_dummy_object()
        app_model = existing_sql_model.to_app_model()

        sql_api.put(app_model, True)

        sql_model = (
            models.QuestionnaireState
            .query
            .filter_by(user_id='someuser')
            .first()
        )

        self.assertEqual(app_model.user_id, sql_model.user_id)
        self.assertEqual(app_model.state_data, sql_model.state)
        self.assertEqual(app_model.version, sql_model.version)


    def test_delete(self):
        sql_model = _save_dummy_object()

        sql_api.delete(sql_model.to_app_model())

        self.assertFalse(
            models.QuestionnaireState
            .query
            .filter_by(user_id='someuser')
            .first()
        )


def _save_dummy_object():
    sql_model = models.QuestionnaireState('someuser', 'data', 1)
    # pylint: disable=maybe-no-member
    models.db.session.add(sql_model)
    models.db.session.commit()

    return sql_model
