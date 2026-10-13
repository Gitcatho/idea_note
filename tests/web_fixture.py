"""Local browser fixture: synthetic records only, never production credentials."""
import sys
from webapp import create_app
from waitress import serve

app = create_app(sys.argv[1], 'http://127.0.0.1:4311')
with app.extensions['auth'].connection() as db:
    initialized = db.execute('SELECT 1 FROM admin').fetchone()
if not initialized:
    app.extensions['auth'].set_password('browser-test-only-12345')
serve(app, host='127.0.0.1', port=4311)
