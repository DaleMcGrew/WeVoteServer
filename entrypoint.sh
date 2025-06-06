#!/usr/local/bin/bash

. venv/bin/activate
# cp --update config/environment_variables-template.json config/environment_variables.json
# which pip
# which python
pip install --requirement requirements.txt
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser --no-input || echo "Superuser already created."
python manage.py runserver 0.0.0.0:8000
