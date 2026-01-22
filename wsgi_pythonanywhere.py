import os
import sys

# ----- YOUR APP LOCATION -----
path = '/home/Wfinch80/inventory'
if path not in sys.path:
    sys.path.append(path)

# ----- ENVIRONMENT SETTINGS (since you don't have the panel) -----
os.environ['SESSION_SECRET'] = 'change_this_to_anything'
os.environ['DATABASE_URL'] = 'sqlite:////home/Wfinch80/inventory/data.db'

# ----- LOAD FLASK APP -----
from app import app as application
