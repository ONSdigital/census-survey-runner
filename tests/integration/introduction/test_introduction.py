from tests.integration.integration_test_case import IntegrationTestCase


class TestIntroduction(IntegrationTestCase):

    def test_mail_link_contains_ru_ref_in_subject(self):
        # Given a business survey
        self.launchSurvey('test', '0102')

        # When on the landing page
        # Then the email link is present with the ru_ref in the subject
        self.assertRegexPage(r'\"mailto\:.+\?subject\=.+123456789012A\"')

    def test_intro_description_displayed(self):
        # Given survey containing intro description
        self.launchSurvey('test', 'introduction')

        # When on the introduction page
        # Then description should be displayed
        self.assertInPage('qa-intro-description')

    def test_intro_description_not_displayed(self):
        # Given survey without introduction description
        self.launchSurvey('test', 'textfield')

        # When on the introduction page
        # Then description should not be displayed
        self.assertNotInPage('qa-intro-description')
