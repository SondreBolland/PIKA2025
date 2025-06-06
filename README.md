# PIKA 2025 Test Service
This is a lightweight web-based survey system built with Flask. It supports configurable surveys stored as JSON files, user session handling, answer storage, and result rendering including optional scoring.

## Requirements

This project uses Python 3 and requires the following libraries:

- Flask
- Werkzeug (comes with Flask)
- SQLite3 (standard library)
- [Optional] Flask-Mail if you enable mailing support

You can install required packages via pip:

```bash
pip install flask
```

## How to run PIKA 2025
Run the following commands from the repo's root folder:
```bash
python main.py init_db
python main.py add pika_eng.json
python main.py
```
This will run the survey on `[http://127.0.0.1:5000](http://127.0.0.1:5000)`/`[http://localhost:5000](http://localhost:5000)`.

### Access the test
Now the test should be running here: `[http://localhost:5000/enter/pika](http://localhost:5000/enter/pika)`.

---

### File Structure
* main.py – Main Flask application
* db.py – Database access layer
* data.py – JSON and survey file utilities
* session.py – Handles user tokens and survey progress
* mail.py – Optional email utility
* templates/ – Jinja2 HTML templates
* config/ – JSON survey definitions and code snippets
* static/ – CSS, JavaScript, and SyntaxHighlighter assets
