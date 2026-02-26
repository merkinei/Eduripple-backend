web: python init_data.py && gunicorn -w 4 -b 0.0.0.0:$PORT --timeout 120 --access-logfile - --error-logfile - "wsgi:app"
release: python init_data.py
