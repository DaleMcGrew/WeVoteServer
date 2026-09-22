#!/usr/bin/env python
"""
Standalone test runner for import_export_jira tests that don't require database.
Run this script to test the core functionality without needing PostgreSQL running.
"""

import sys
import os
import unittest
from unittest.mock import Mock, MagicMock

# Add the project directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Mock Django imports before importing our modules
sys.modules['django'] = MagicMock()
sys.modules['django.db'] = MagicMock()
sys.modules['django.db.models'] = MagicMock()
sys.modules['django.test'] = MagicMock()
sys.modules['wevote_functions'] = MagicMock()
sys.modules['wevote_functions.functions'] = MagicMock()

from datetime import datetime

# Import the modules we're testing
from import_export_jira.controllers import (
    format_date, sanitize_jira_label, JiraSubTask, JiraStory, JiraEpic,
    retry_on_jira_error
)
from jira.exceptions import JIRAError


class TestFormatDate(unittest.TestCase):
    """Test format_date utility function."""

    def test_format_datetime(self):
        dt = datetime(2024, 3, 15, 10, 30, 0)
        result = format_date(dt)
        self.assertEqual(result, '2024-03-15T10:30:00')

    def test_format_string(self):
        result = format_date('2024-03-15')
        self.assertEqual(result, '2024-03-15')

    def test_format_none(self):
        result = format_date(None)
        self.assertIsNone(result)


class TestSanitizeJiraLabel(unittest.TestCase):
    """Test sanitize_jira_label utility function."""

    def test_sanitize_spaces(self):
        result = sanitize_jira_label('2024 Primary Election')
        # Labels starting with numbers get underscore prefix
        self.assertEqual(result, '_2024_Primary_Election')

    def test_sanitize_special_characters(self):
        result = sanitize_jira_label('Test@Label#123!')
        self.assertEqual(result, 'TestLabel123')

    def test_sanitize_starts_with_number(self):
        result = sanitize_jira_label('2024Election')
        self.assertEqual(result, '_2024Election')

    def test_sanitize_empty_string(self):
        result = sanitize_jira_label('')
        self.assertEqual(result, '')

    def test_sanitize_valid_characters(self):
        result = sanitize_jira_label('Valid_Label-123.test')
        # Valid characters are preserved (starts with letter, no prefix needed)
        self.assertEqual(result, 'Valid_Label-123.test')


class TestJiraDataClasses(unittest.TestCase):
    """Test JIRA dataclasses."""

    def test_jira_subtask_to_dict(self):
        subtask = JiraSubTask(
            task_type='email',
            task_url='http://example.com',
            state='CA',
            due_date=datetime(2024, 11, 5)
        )
        result = subtask.to_dict()
        self.assertEqual(result['task_type'], 'email')
        self.assertEqual(result['state'], 'CA')
        self.assertIn('2024-11-05', result['due_date'])

    def test_jira_story_to_dict(self):
        story = JiraStory(
            story_title='Test Story',
            office='Governor',
            candidate_name='John Doe',
            candidate_id='CA-GOV-001',
            jurisdiction='Statewide',
            state='CA'
        )
        result = story.to_dict()
        self.assertEqual(result['story_title'], 'Test Story')
        self.assertEqual(result['candidate_name'], 'John Doe')
        self.assertEqual(result['sub_tasks'], [])

    def test_jira_epic_add_story(self):
        epic = JiraEpic(
            epic_title='Test Epic',
            election_date=datetime(2024, 11, 5),
            election_name='2024 General',
            election_id='2024-GEN',
            election_report_url='http://example.com'
        )
        story = JiraStory(
            story_title='Test',
            office='Gov',
            candidate_name='Doe',
            candidate_id='001',
            jurisdiction='State',
            state='CA'
        )
        epic.add_story(story)
        self.assertEqual(epic.get_total_candidates(), 1)


class TestRetryLogic(unittest.TestCase):
    """Test retry and backoff logic."""

    def test_retry_on_rate_limit(self):
        mock_func = Mock()
        error = JIRAError(status_code=429, text="Rate limited")
        mock_func.side_effect = [error, "success"]

        decorated = retry_on_jira_error(max_retries=1, initial_delay=0.01)(mock_func)
        result = decorated()

        self.assertEqual(result, "success")
        self.assertEqual(mock_func.call_count, 2)

    def test_no_retry_on_client_error(self):
        mock_func = Mock()
        error = JIRAError(status_code=400, text="Bad request")
        mock_func.side_effect = error

        decorated = retry_on_jira_error(max_retries=3, initial_delay=0.01)(mock_func)

        with self.assertRaises(JIRAError):
            decorated()

        self.assertEqual(mock_func.call_count, 1)

    def test_retry_exhaustion(self):
        mock_func = Mock()
        error = JIRAError(status_code=500, text="Server error")
        mock_func.side_effect = error

        decorated = retry_on_jira_error(max_retries=2, initial_delay=0.01)(mock_func)

        with self.assertRaises(JIRAError):
            decorated()

        self.assertEqual(mock_func.call_count, 3)


if __name__ == '__main__':
    # Run the tests
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestFormatDate))
    suite.addTests(loader.loadTestsFromTestCase(TestSanitizeJiraLabel))
    suite.addTests(loader.loadTestsFromTestCase(TestJiraDataClasses))
    suite.addTests(loader.loadTestsFromTestCase(TestRetryLogic))

    # Run with verbose output
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Exit with appropriate code
    sys.exit(0 if result.wasSuccessful() else 1)
