import glob
from pathlib import Path
from doit.tools import create_folder
import tomllib

DOIT_CONFIG = {"default_tasks": ['html']}
PODEST = 'habit/locale'
PROJECT_DIR = Path(__file__).parent


def task_pot():
    return {
        'actions': [f'pybabel extract -o {PODEST}/messages.pot habit/bot'],
        'targets': [f"{PODEST}/messages.pot"],
    }
