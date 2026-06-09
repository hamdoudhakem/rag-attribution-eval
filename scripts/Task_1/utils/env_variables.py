import os
from dotenv import load_dotenv

base_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(base_dir, os.pardir, ".env")

load_dotenv(dotenv_path=env_path)

# if you require it to exist:
CONTACT_EMAIL = os.environ['CONTACT_EMAIL']
