# politician/migrations/0002_enable_pg_trgm.py
# Brought to you by We Vote. Be good.
# -*- coding: UTF-8 -*-

from django.db import migrations
from django.contrib.postgres.operations import TrigramExtension, BtreeGistExtension


class Migration(migrations.Migration):

    dependencies = [
        ('politician', '0001_initial'),
    ]

    operations = [
        TrigramExtension(),  # Enables pg_trgm extension
        BtreeGistExtension(),  # For GiST index support
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS politician_name_trgm_idx ON politician_politician "
            "USING gist(politician_name gist_trgm_ops);",
            "DROP INDEX IF EXISTS politician_name_trgm_idx;"
        ),

    ]
