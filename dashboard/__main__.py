import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dashboard.app import app

if __name__ == "__main__":
    app.run(debug=False, port=8050)
