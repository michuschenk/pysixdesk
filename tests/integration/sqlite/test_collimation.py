import unittest
import os
import shutil
import sys
from pathlib import Path
# give the test runner the import access
pysixdesk_path = str(Path(__file__).parents[3].absolute())
sys.path.insert(0, pysixdesk_path)
# setting environment variable for htcondor job.
if 'PYTHONPATH' in os.environ.keys():
    os.environ['PYTHONPATH'] = f"{pysixdesk_path}:{os.environ['PYTHONPATH']}"
else:
    os.environ['PYTHONPATH'] = f"{pysixdesk_path}"
import pysixdesk

from .test_sqlite import SQLiteStudy


class SQLiteDBColl(SQLiteStudy, unittest.TestCase):
    def setUp(self):
        self.test_folder = Path('integration_test/sqlite_coll')
        self.test_folder.mkdir(parents=True, exist_ok=True)
        self.ws_name = 'integration_test'
        self.ws = pysixdesk.WorkSpace(str(self.test_folder / self.ws_name))
        self.st_name = 'sqlite_coll'
        self.st = None

    def test_sqlite_study(self):
        self.sqlite_study(config='SQLiteCollConfig')
        # add additional checks

    def tearDown(self):
        # remove directory
        shutil.rmtree('integration_test', ignore_errors=True)


if __name__ == '__main__':
    unittest.main()
