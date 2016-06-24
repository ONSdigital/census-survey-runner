import unittest
from app import create_app
from tests.integration.create_token import create_token


class TestPageErrors(unittest.TestCase):
    def setUp(self):
        self.application = create_app('development')
        self.client = self.application.test_client()

    def test_happy_path(self):
        # Get a token
        eq_id = "1"
        token = create_token("999", eq_id)
        resp = self.client.get('/session?token=' + token.decode(), follow_redirects=True)
        self.assertEquals(resp.status_code, 200)

        # We are on the landing page
        content = resp.get_data(True)

        self.assertRegexpMatches(content, '<title>Introduction</title>')
        self.assertRegexpMatches(content, '>Get Started<')
        self.assertRegexpMatches(content, '>Test Survey<')

        # We proceed to the questionnaire
        post_data = {
            'action[start_questionnaire]': 'Start Questionnaire'
        }
        resp = self.client.post('/questionnaire/' + eq_id + '/789/introduction', data=post_data, follow_redirects=False)
        self.assertEquals(resp.status_code, 302)

        page_one_url = resp.headers['Location']

        resp = self.client.get(page_one_url, follow_redirects=False)
        self.assertEquals(resp.status_code, 200)

        # We are in the Questionnaire
        content = resp.get_data(True)
        self.assertRegexpMatches(content, '<title>Survey</title>')
        self.assertRegexpMatches(content, ">What are the dates of the retail spending period you are reporting for\?</")
        self.assertRegexpMatches(content, ">Save &amp; Continue<")

        # We fill in our answers
        form_data = {
            # Start Date
            "1ce2045f-e773-4ef4-9767-a864cbfc8577-day": "01",
            "1ce2045f-e773-4ef4-9767-a864cbfc8577-month": "4",
            "1ce2045f-e773-4ef4-9767-a864cbfc8577-year": "2016",
            # End Date
            "fa0e74dc-cd84-45b8-8761-23bb1f4af1cb-day": "30",
            "fa0e74dc-cd84-45b8-8761-23bb1f4af1cb-month": "04",
            "fa0e74dc-cd84-45b8-8761-23bb1f4af1cb-year": "2016",
            # Preferred contact number
            "ddd33acb-3d9c-4b27-b99e-1407935cdd16": "01234567890",
            # Total Food
            "047cf8f5-e9c4-4a6c-a3f0-293bdf54dd0d": "250",
            # Total Alchohol, Confectionary and Tobacco
            "8075e95f-cfb4-40e4-bc1c-f90b373ca22a": "100",
            # Clothing and footwear
            "b01820e9-7437-4383-a557-48d736898924": "50",
            # Total Retail spending
            "f77ae356-6f42-4afe-a476-747b1aab4a6c": "400",
            # User Action
            "action[save_continue]": "Save &amp; Continue"
        }

        # We submit the form
        resp = self.client.post(page_one_url, data=form_data, follow_redirects=False)
        self.assertEquals(resp.status_code, 302)

        # There are no validation errors
        self.assertNotEquals(resp.headers['Location'], page_one_url)

        # On to page two
        page_two_url = resp.headers['Location']

        resp = self.client.get(page_two_url, follow_redirects=False)
        self.assertEquals(resp.status_code, 200)

        # We are in the Questionnaire
        content = resp.get_data(True)
        self.assertRegexpMatches(content, '<title>Survey</title>')
        self.assertRegexpMatches(content, ">How many rooms are available for use only by your household\?</")
        self.assertRegexpMatches(content, ">Save &amp; Continue<")

        # We fill in our answers except one
        form_data = {
            # People in household
            "a5c43b5b-f6e9-412f-834d-2d6cc83b5436": '',  # missing
            # Overnight
            "d5f9db59-9cc0-433f-9318-39f83b63d4d8": 5,
            # number of rooms
            "863d4afa-17e8-4537-bbae-65d19a6894c1": 8,
            # User Action
            "action[save_continue]": "Save &amp; Continue"
        }

        # We submit the form
        resp = self.client.post(page_two_url, data=form_data, follow_redirects=False)
        self.assertEquals(resp.status_code, 302)

        # There are validation errors
        self.assertEquals(resp.headers['Location'], page_two_url)

        # Go back to the first page
        resp = self.client.get(page_one_url, follow_redirects=False)
        self.assertEquals(resp.status_code, 200)

        # We fill in our answers missing one required field
        form_data = {
            # Start Date
            "1ce2045f-e773-4ef4-9767-a864cbfc8577-day": "01",
            "1ce2045f-e773-4ef4-9767-a864cbfc8577-month": "4",
            "1ce2045f-e773-4ef4-9767-a864cbfc8577-year": "2016",
            # End Date
            "fa0e74dc-cd84-45b8-8761-23bb1f4af1cb-day": "30",
            "fa0e74dc-cd84-45b8-8761-23bb1f4af1cb-month": "04",
            "fa0e74dc-cd84-45b8-8761-23bb1f4af1cb-year": "2016",
            # Preferred contact number
            "ddd33acb-3d9c-4b27-b99e-1407935cdd16": "",  # Missing
            # Total Food
            "047cf8f5-e9c4-4a6c-a3f0-293bdf54dd0d": "250",
            # Total Alchohol, Confectionary and Tobacco
            "8075e95f-cfb4-40e4-bc1c-f90b373ca22a": "100",
            # Clothing and footwear
            "b01820e9-7437-4383-a557-48d736898924": "50",
            # Total Retail spending
            "f77ae356-6f42-4afe-a476-747b1aab4a6c": "400",
            # User Action
            "action[save_continue]": "Save &amp; Continue"
        }

        # We submit the form
        resp = self.client.post(page_one_url, data=form_data, follow_redirects=False)
        self.assertEquals(resp.status_code, 302)

        # We have a validation error
        self.assertEquals(resp.headers['Location'], page_one_url)
        resp = self.client.get(page_one_url, follow_redirects=False)
        self.assertEquals(resp.status_code, 200)

        content = resp.get_data(True)
        self.assertRegexpMatches(content, '<a href="#ddd33acb-3d9c-4b27-b99e-1407935cdd16">Go to this error')
        # We DO NOT have the error from page two
        self.assertNotRegexpMatches(content, '<a href="#a5c43b5b-f6e9-412f-834d-2d6cc83b5436">Go to this error')
