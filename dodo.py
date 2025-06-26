import glob
from pathlib import Path
from doit.tools import create_folder
import tomllib

DOIT_CONFIG = {"default_tasks": ['html']}
PODEST = 'habit/locale'
PROJECT_DIR = Path(__file__).parent


