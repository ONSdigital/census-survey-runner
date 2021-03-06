import time

from app import settings
from tests.integration.integration_test_case import IntegrationTestCase


class TestTimeout(IntegrationTestCase):

    def setUp(self):
        settings.EQ_SESSION_TIMEOUT_SECONDS = 1
        settings.EQ_SESSION_TIMEOUT_GRACE_PERIOD_SECONDS = 0
        super().setUp()

    def tearDown(self):
        settings.EQ_SESSION_TIMEOUT_SECONDS = 45 * 60
        settings.EQ_SESSION_TIMEOUT_GRACE_PERIOD_SECONDS = 30
        super().tearDown()

    def test_timeout_continue_returns_200(self):
        self.launchSurvey('test', 'timeout')
        self.get('/timeout-continue')
        self.assertStatusOK()

    def test_when_session_times_out_server_side_401_is_returned(self):
        self.launchSurvey('test', 'timeout')
        time.sleep(2)
        self.get(self.last_url)
        self.assertStatusUnauthorised()

    def test_schema_defined_timeout_is_used(self):
        self.launchSurvey('test', 'timeout')
        self.assertInPage('window.__EQ_SESSION_TIMEOUT__ = 1')

    def test_schema_defined_timeout_cant_be_higher_than_server(self):
        self._application.config['EQ_SESSION_TIMEOUT_SECONDS'] = 10
        self.launchSurvey('test', 'timeout')
        self.assertInPage('window.__EQ_SESSION_TIMEOUT__ = 6')
