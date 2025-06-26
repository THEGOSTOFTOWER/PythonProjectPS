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

def task_po():
    return {
        'actions': [f"pybabel update -l ru -D messages -i {PODEST}/messages.pot -d {PODEST}"],
        'file_dep': [f'{PODEST}/messages.pot'],
        'targets': [f"{PODEST}/ru/LC_MESSAGES/messages.po"],
    }

def task_mo():
    """Compile translations."""
    return {
            'actions': [
                (create_folder, [f'{PODEST}/ru/LC_MESSAGES']),
                f'pybabel compile -D messages -l ru -i {PODEST}/ru/LC_MESSAGES/messages.po -d {PODEST}'
                       ],
            'file_dep': [f'{PODEST}/ru/LC_MESSAGES/messages.po'],
            'targets': [f'{PODEST}/ru/LC_MESSAGES/messages.mo'],
            'task_dep': ['po']
           }
