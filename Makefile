PYTHON ?= .venv/bin/python

.PHONY: install migrate check test test-serial test-ui test-package package schema-check run static demo demo-map billing-month
install:
	python3 scripts/bootstrap.py
migrate:
	$(PYTHON) manage.py migrate
check:
	$(PYTHON) manage.py check
	$(PYTHON) manage.py makemigrations --check --dry-run
	node --check static/cemetery/app.js
test:
	$(PYTHON) manage.py test cemetery.tests --verbosity 2
test-serial:
	$(PYTHON) manage.py test cemetery.tests --settings=config.settings_verify --verbosity 2
test-ui:
	npm test
test-package:
	$(PYTHON) -m unittest discover -s scripts/tests -v
package:
	$(PYTHON) scripts/package_release.py
schema-check:
	$(PYTHON) scripts/verify_postgres_schema.py
run:
	$(PYTHON) manage.py runserver 127.0.0.1:8000
demo:
	$(PYTHON) scripts/run_academic.py
demo-map:
	DJANGO_SETTINGS_MODULE=config.settings_academic $(PYTHON) manage.py migrate --noinput
	DJANGO_SETTINGS_MODULE=config.settings_academic $(PYTHON) manage.py expand_demo_map
billing-month:
	DJANGO_SETTINGS_MODULE=config.settings_academic $(PYTHON) manage.py migrate --noinput
	DJANGO_SETTINGS_MODULE=config.settings_academic $(PYTHON) manage.py generate_monthly_invoices $(if $(MONTH),--month $(MONTH),)
static:
	$(PYTHON) manage.py collectstatic --noinput
