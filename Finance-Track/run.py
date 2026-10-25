import os
from dotenv import load_dotenv

load_dotenv()

from app import create_app

config_name = os.environ.get('FLASK_ENV', 'development')
app = create_app(config_name)

if __name__ == '__main__':
    debug = config_name == 'development'
    app.run(debug=debug, host='0.0.0.0', port=8000)
