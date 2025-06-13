#!/usr/local/bin/bash

. venv/bin/activate
pip install --requirement requirements.dev.txt
python set_env_variables.py
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser --no-input || echo "Superuser already created."
python manage.py runserver 0.0.0.0:8000
