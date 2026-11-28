# Testing Guide for import_export_jira

## Prerequisites

Make sure you have the virtual environment activated:
```bash
source venv/bin/activate
```

## Running Tests

### Option 1: Run with PostgreSQL (Requires DB Running)

If PostgreSQL is running:
```bash
# Run all tests for this app
python manage.py test import_export_jira --verbosity=2

# Run specific test class
python manage.py test import_export_jira.tests.FormatDateTests --verbosity=2

# Run specific test method
python manage.py test import_export_jira.tests.FormatDateTests.test_format_datetime --verbosity=2
```

### Option 2: Start PostgreSQL First

Check if PostgreSQL is running:
```bash
sudo systemctl status postgresql
```

Start PostgreSQL if needed:
```bash
sudo systemctl start postgresql
```

Then run tests as shown in Option 1.

### Option 3: Run Tests Without Database (Standalone)

For tests that don't require database (most of our unit tests), you can run them directly with pytest or unittest:

```bash
# Install pytest if not already installed
pip install pytest pytest-django

# Run with pytest
pytest import_export_jira/tests.py -v

# Or use Python's unittest
python -m unittest import_export_jira.tests -v
```

### Option 4: Use SQLite for Testing (Quick Setup)

Temporarily use SQLite for tests by setting environment variable:
```bash
# Create a test settings file or use SQLite
DJANGO_SETTINGS_MODULE=config.test_settings python manage.py test import_export_jira
```

## Test Coverage

Our test suite includes:

### Unit Tests (No Database Required)
- `FormatDateTests` - Date formatting utilities (3 tests)
- `SanitizeJiraLabelTests` - Label sanitization (5 tests)
- `JiraDataClassTests` - Dataclass serialization (3 tests)
- `JiraExcelLoaderTests` - File parsing validation, CSV support, dynamic subtasks (11 tests)
- `RetryLogicTests` - Retry/backoff logic (3 tests)

### Integration Tests (Database Required)
- `JiraApiCounterTests` - Database model operations (3 tests)
- `JiraApiControlTests` - API control with rate limiting (3 tests)

## Expected Output

When all tests pass, you should see:
```
Found 34 test(s).
Creating test database for alias 'default'...
test_format_datetime (import_export_jira.tests.FormatDateTests) ... ok
test_format_none (import_export_jira.tests.FormatDateTests) ... ok
test_format_string (import_export_jira.tests.FormatDateTests) ... ok
[... more tests ...]
----------------------------------------------------------------------
Ran 34 tests in X.XXXs

OK
Destroying test database for alias 'default'...
```

## Troubleshooting

### PostgreSQL Connection Error
If you get "connection refused" error:
1. Check PostgreSQL status: `sudo systemctl status postgresql`
2. Start it: `sudo systemctl start postgresql`
3. Verify it's listening: `sudo netstat -plnt | grep 5432`

### Missing Dependencies
If you get import errors:
```bash
pip install jira pandas openpyxl
```

### Permission Issues
If you get permission denied:
```bash
# Check PostgreSQL user permissions
sudo -u postgres psql -c "ALTER USER wevoteserverdb_user CREATEDB;"
```

## Manual Testing

To manually test the JIRA import functionality:

1. Start the Django server:
   ```bash
   python manage.py runserver
   ```

2. Set environment variables:
   ```bash
   export JIRA_URL="https://your-jira-instance.atlassian.net"
   export JIRA_USERNAME="your-email@example.com"
   export JIRA_API_TOKEN="your-api-token"
   export JIRA_PROJECT_KEY="YOUR_PROJECT_KEY"
   ```

3. Navigate to: http://localhost:8000/import_export_jira/import_jira_elections/

4. Upload an Excel (.xlsx) or CSV (.csv) file

5. Configure subtask count and names in the UI (0-4 subtasks per story)

6. Preview or Import

## Dynamic Subtasks

The UI lets you configure 0-4 subtasks per story:
1. Set the number of subtasks (0-4)
2. For each subtask, enter a description (e.g., "Research Candidate", "Verify Address")
3. Subtask URLs are read from columns 14-17 of the data file, mapped positionally to the configured names
4. Only non-empty URL columns create actual subtask objects

## File Format Support

Both **Excel (.xlsx, .xls)** and **CSV (.csv)** files are supported. Format is auto-detected from the file extension. Use `file_format='csv'` or `file_format='excel'` to override.

## Test Data

For loader tests, you can create a test file with this structure:
- Row 1-2: Headers (ignored)
- Row 3+: Data with 14+ columns:
  - Column 0: Election Date
  - Column 1: Epic Title
  - Column 2: Election Name
  - Columns 3-13: Other metadata (see `COL_*` constants in `controllers.py`)
  - Columns 14-17: Subtask URLs (mapped to user-configured subtask names)

Example test file creation:
```python
import pandas as pd

data = [
    ['Header1', 'Header2', ...],  # Row 1
    ['Header1', 'Header2', ...],  # Row 2
    ['2024-11-05', '2024 General: Test', 'General Election', 'TEST-001', ...]  # Data
]
df = pd.DataFrame(data)
df.to_excel('test_election_data.xlsx', index=False, header=False)
df.to_csv('test_election_data.csv', index=False, header=False)
```
