import os
from flask import Flask, request

app = Flask(__name__)
@app.route('/')
def index():
    return 'flask is opening !'

if __name__ == '__main__':
    port = os.getenv('port', 5000)
    app.run(host='0.0.0.0', port=port, debug=True)
