from unittest.mock import Mock, patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import Candidate, Interaction


class CandidateAccessCharacterizationTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user('owner', password='password')
        self.recruiter = User.objects.create_user('recruiter', password='password')
        self.other_recruiter = User.objects.create_user(
            'other-recruiter', password='password'
        )
        self.public_candidate = Candidate.objects.create(
            user=self.owner,
            name='Public Candidate',
            email='public@example.com',
            resume='Verified resume text',
            public_profile=True,
            activate=True,
        )
        self.private_candidate = Candidate.objects.create(
            name='Private Candidate',
            email='private@example.com',
            resume='Private resume text',
            public_profile=False,
            activate=False,
        )

    def test_candidate_management_requires_authentication(self):
        response = self.client.get(reverse('manager_candidate'))

        self.assertRedirects(
            response,
            f"{reverse('login')}?next={reverse('manager_candidate')}",
        )

    def test_candidate_update_is_scoped_to_logged_in_owner(self):
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse('manager_candidate'),
            {
                'name': 'Updated Candidate',
                'email': 'updated@example.com',
                'phone': '',
                'linkedin': '',
                'public_profile': 'on',
            },
        )

        self.assertRedirects(response, reverse('profile'))
        self.public_candidate.refresh_from_db()
        self.private_candidate.refresh_from_db()
        self.assertEqual(self.public_candidate.name, 'Updated Candidate')
        self.assertEqual(self.public_candidate.user, self.owner)
        self.assertEqual(self.private_candidate.name, 'Private Candidate')

    def test_discovery_lists_only_public_profiles(self):
        self.client.force_login(self.recruiter)

        response = self.client.get(reverse('candidates'))

        self.assertContains(response, self.public_candidate.name)
        self.assertNotContains(response, self.private_candidate.name)

    def test_direct_chat_currently_allows_non_public_inactive_candidate(self):
        self.client.force_login(self.recruiter)

        response = self.client.get(reverse('chat', args=[self.private_candidate.slug]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.private_candidate.email)

    def test_chat_history_is_scoped_to_logged_in_recruiter(self):
        Interaction.objects.create(
            user=self.recruiter,
            candidate=self.public_candidate,
            question='My question',
            response='My response',
        )
        Interaction.objects.create(
            user=self.other_recruiter,
            candidate=self.public_candidate,
            question='Another recruiter secret',
            response='Another response',
        )
        self.client.force_login(self.recruiter)

        response = self.client.get(
            reverse('chat', args=[self.public_candidate.slug])
        )

        self.assertContains(response, 'My question')
        self.assertNotContains(response, 'Another recruiter secret')

    @patch('chatbot.views.resumebot')
    def test_chat_persists_a_provider_response_for_the_current_user(
        self, resumebot
    ):
        resumebot.run = Mock(return_value='Grounded response')
        self.client.force_login(self.recruiter)

        response = self.client.post(
            reverse('chat', args=[self.public_candidate.slug]),
            {'question': 'What have you done?'},
        )

        self.assertEqual(response.status_code, 200)
        interaction = Interaction.objects.get()
        self.assertEqual(interaction.user, self.recruiter)
        self.assertEqual(interaction.candidate, self.public_candidate)
        self.assertEqual(interaction.question, 'What have you done?')
        self.assertEqual(interaction.response, 'Grounded response')
        resumebot.run.assert_called_once()
