from flask import Flask, request

def init_app():
    app = Flask(__name__)
    @app.route('/')
    def index():
        return 'flask is opening !'

    port = os.getenv('port', 5000)
    app.run(host='0.0.0.0', port=port, debug=True)

if __name__ == '__main__':
    init_app()
