from app import create_app
import os
from datetime import datetime

app = create_app()
app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'uploads')

@app.template_filter('datetime')
def format_datetime(value):
    """Convert datetime string to formatted string"""
    try:
        return datetime.strptime(value, '%Y-%m-%dT%H:%M:%S').strftime('%Y-%m-%d %H:%M')
    except (ValueError, TypeError):
        return value

if __name__ == '__main__':
    app.run(debug=True, port=5000)