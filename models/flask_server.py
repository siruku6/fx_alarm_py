import os
from flask          import Flask, request
from logging.config import dictConfig

def set_logger():
    # https://qiita.com/sky_jokerxx/items/15b2be7a97342988d734
    dictConfig({
        'version': 1,
        'formatters': {
            'file': {
                'format': '[%(asctime)s] %(levelname)s in %(module)s: %(message)s',
            }
        },
        'handlers': {
            'file': {
                'class': 'logging.handlers.TimedRotatingFileHandler',
                'formatter': 'file',
                'filename': './log/flask.log',
                'backupCount': 3,
                'when': 'D',
            }
        },
        'root': {
            'level': 'DEBUG',
            'handlers': ['file']
        }
    })

app = Flask(__name__)
@app.route('/')
def index():
    return 'flask is opening !'

# file_name
if __name__ == 'flask_server':
    set_logger()

if __name__ == '__main__':
    port = os.getenv('port', 5000)
    app.run(host='0.0.0.0', port=port, debug=True)
