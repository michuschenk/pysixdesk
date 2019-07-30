import unittest
import shutil
import logging
from pathlib import Path
import sys
# give the test runner the import access
sys.path.insert(0, Path(__file__).parents[1].absolute())
from pysixdesk.lib import workspace

# disable logging
# one print remains as the config.py gets imported which
# overrides these logger settings.
logging.getLogger('pysixdesk').setLevel(logging.CRITICAL)


class WorkSpaceTest(unittest.TestCase):

    def setUp(self):
        self.test_folder = Path('unit_test/workspace/')
        self.test_folder.mkdir(parents=True, exist_ok=True)
        self.ws = workspace.WorkSpace(str(self.test_folder / 'unittest_ws'))
        self.st = None

    def test_init_load(self):
        paths_out = {'workspace': str((self.test_folder / 'unittest_ws').absolute()),
                     'studies'  : str((self.test_folder / 'unittest_ws/studies').absolute()),
                     'templates': str((self.test_folder / 'unittest_ws/templates').absolute())}
        self.assertEqual(self.ws.studies, [])
        self.assertEqual(self.ws.paths, paths_out)

        self.ws.init_study('unittest_st')
        paths_out = {'workspace': str((self.test_folder / 'unittest_ws').absolute()),
                     'studies'  : str((self.test_folder / 'unittest_ws/studies').absolute()),
                     'templates': str((self.test_folder / 'unittest_ws/templates').absolute())}
        self.assertEqual(self.ws.studies, ['unittest_st'])
        self.assertEqual(self.ws.paths, paths_out)

        # default config.py
        self.st = self.ws.load_study('unittest_st')

        load_tables = [('boinc_vars',),
                       ('env',),
                       ('oneturn_sixtrack_result',),
                       ('oneturn_sixtrack_wu',),
                       ('preprocess_task',),
                       ('preprocess_wu',),
                       ('six_results',),
                       ('sixtrack_task',),
                       ('sixtrack_wu',),
                       ('templates',)]
        self.assertEqual(self.st.db.fetch_tables(), load_tables)
        # is there a better way to test this ?
        self.assertIsNotNone(self.st)

    def tearDown(self):
        if self.st is not None and self.st.db_info['db_type'] == 'mysql':
            conn = self.st.db.conn
            with conn.cursor() as c:
                sql = "DROP DATABASE unittest_ws_unittest_st;"
                c.execute(sql)

        shutil.rmtree(self.test_folder.parents[0], ignore_errors=True)


if __name__ == '__main__':
    unittest.main()
