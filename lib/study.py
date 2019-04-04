import os
import io
import sys
import time
import copy
import shutil
import inspect
import itertools
import configparser
import collections
import importlib
import utils
import mad6t_oneturn
import gather
import sixtrack

from importlib.machinery import SourceFileLoader
from pysixdb import SixDB

class Study(object):

    def __init__(self, name='example_study', loc=os.getcwd()):
        '''Constructor'''
        self.name = name
        self.location = os.path.abspath(loc)
        self.study_path = os.path.join(self.location, self.name)
        self.config = configparser.ConfigParser()
        self.config.optionxform = str #preserve case
        self.mad6t_joblist = []
        self.sixtrack_joblist = []
        #All the requested parameters for a study
        self.paths = {}
        self.madx_params = {}
        self.madx_input = {}
        self.madx_output = {}
        self.oneturn_sixtrack_params = {}
        self.oneturn_sixtrack_input = {}
        self.oneturn_sixtrack_output = {}
        self.sixtrack_params = {}
        self.sixtrack_input = {}
        self.sixtrack_output = []
        self.tables = {}
        self.table_keys = {}
        self.pragma = {}
        self.boinc_vars = collections.OrderedDict()
        #initialize default values
        Study._defaults(self)

    def _defaults(self):
        '''initialize a study with some default settings'''
        #full path to madx
        self.paths["madx_exe"] = "/afs/cern.ch/user/m/mad/bin/madx"
        #full path to sixtrack
        self.paths["sixtrack_exe"] = "/afs/cern.ch/project/sixtrack/build/sixtrack"
        self.paths["study_path"] = self.study_path
        self.paths["madx_in"] = os.path.join(self.study_path, "mad6t_input")
        self.paths["madx_out"] = os.path.join(self.study_path, "mad6t_output")
        self.paths["sixtrack_in"] = os.path.join(self.study_path, "sixtrack_input")
        self.paths["sixtrack_out"] = os.path.join(self.study_path, "sixtrack_output")
        self.paths["gather"] = os.path.join(self.study_path, "gather")
        self.paths["templates"] = self.study_path
        self.paths["boinc_spool"] = "/afs/cern.ch/work/b/boinc/boinc"
        self.htc_temp = 'htcondor_run.sub'

        self.madx_output = {
                'fc.2': 'fort.2',
                'fc.3': 'fort.3.mad',
                'fc.3.aux': 'fort.3.aux',
                'fc.8': 'fort.8',
                'fc.16': 'fort.16',
                'fc.34': 'fort.34'}
        self.oneturn_sixtrack_params = {
                "turnss": 1,
                "nss": 1,
                "ax0s": 0.1,
                "ax1s": 0.1,
                "imc": 1,
                "iclo6": 2,
                "writebins": 1,
                "ratios": 1,
                "Runnam": 'FirstTurn',
                "idfor": 0,
                "ibtype": 0,
                "ition": 0,
                "CHRO": '/',
                "TUNE": '/',
                "POST": 'POST',
                "POS1": '',
                "ndafi": 1,
                "tunex": 62.28,
                "tuney": 60.31,
                "inttunex": 62.28,
                "inttuney": 60.31,
                "DIFF": '/DIFF',
                "DIF1": '/',
                "pmass": 938.272013,
                "emit_beam": 3.75,
                "e0": 7000,
                "bunch_charge": 1.15E11,
                "CHROM": 0,
                "chrom_eps": 0.000001,
                "dp1": 0.000001,
                "dp2": 0.000001,
                "chromx": 2,
                "chromy": 2,
                "TUNEVAL": '/',
                "CHROVAL": '/'}
        self.oneturn_sixtrack_input['input'] = copy.deepcopy(self.madx_output)
        self.oneturn_sixtrack_output = ['fort.10']
        self.sixtrack_output = ['fort.10']

        self.dbname = 'data.db'
        #Default definition of the database tables
        self.tables['templates'] = {}
        self.tables['env'] = {}
        self.tables['mad6t_wu'] = {
                'wu_id': 'int',
                'job_name': 'text',
                'input_file': 'blob',
                'status': 'text',
                'task_id': 'int',
                'mtime': 'float'}
        self.table_keys['mad6t_wu'] = {
                'primary': ['wu_id'],
                'foreign': {},
                }
        self.tables['mad6t_task'] = {
                'task_id': 'int',
                'wu_id': 'int',
                'task_name': 'text',
                'madx_in' : 'blob',
                'madx_stdout': 'blob',
                'job_stdout': 'blob',
                'job_stderr': 'blob',
                'job_stdlog': 'blob',
                'count': 'int',
                'status': 'text',
                'mtime': 'float'}
        self.table_keys['mad6t_task'] = {
                'primary': ['task_id'],
                'foreign': {'mad6t_wu': [['wu_id'], ['wu_id']]},
                }
        self.tables['oneturn_sixtrack_wu'] = {}
        self.tables['sixtrack_wu']={
                'wu_id': 'int',
                'mad6t_id': 'int',
                'job_name': 'text',
                'input_file': 'blob',
                'status': 'text',
                'task_id': 'int',
                'mtime': 'float'}
        self.table_keys['sixtrack_wu'] = {
                'primary': ['wu_id'],
                'foreign': {'mad6t_wu': [['mad6t_id'], ['wu_id']]},
                }
        self.tables['sixtrack_task'] = {
                'task_id': 'int',
                'wu_id': 'int',
                'task_name': 'text',
                'job_stdout': 'blob',
                'job_stderr': 'blob',
                'job_stdlog': 'blob',
                'count': 'int',
                'status': 'text',
                'mtime': 'float'}
        self.table_keys['sixtrack_task'] = {
                'primary': ['task_id'],
                'foreign': {'sixtrack_wu': [['wu_id'], ['wu_id']]},
                }
        self.tables['boinc_vars'] = {}
        self.tables['result'] = {
                'betax': 'float',
                'betay': 'float'}#TODO
        self.db_settings = {
                'synchronous': 'off',
                'foreign_keys': 'on',
                'journal_mode': 'memory',
                'auto_vacuum': 'full',
                'temp_store': 'memory',
                'count_changes': 'off'}

        self.boinc_vars['workunitName'] = 'sixdesk'
        self.boinc_vars['fpopsEstimate'] = 30*2*10e5/2*10e6*6
        self.boinc_vars['fpopsBound'] = self.boinc_vars['fpopsEstimate']*1000
        self.boinc_vars['memBound'] = 100000000
        self.boinc_vars['diskBound'] = 200000000
        self.boinc_vars['delayBound'] = 2400000
        self.boinc_vars['redundancy'] = 2
        self.boinc_vars['copies'] = 2
        self.boinc_vars['errors'] = 5
        self.boinc_vars['numIssues'] = 5
        self.boinc_vars['resultsWithoutConcensus'] = 3
        self.boinc_vars['appName'] = 'sixtrack'

    def update_tables(self):
        '''Update the database tables after the user define the necessary
        variables. This method should be called before 'structure()'
        '''
        for key in self.madx_params.keys():
            self.tables['mad6t_wu'][key] = 'INT'
        for key in self.madx_output.values():
            self.tables['mad6t_task'][key] = 'BLOB'

        for key in self.oneturn_sixtrack_params.keys():
            self.tables['oneturn_sixtrack_wu'][key] = 'INT'

        for key in self.sixtrack_params.keys():
            self.tables['sixtrack_wu'][key] = 'INT'
        for key in self.sixtrack_output:
            self.tables['sixtrack_task'][key] = 'BLOB'

        for key in self.madx_input.keys():
            self.tables['templates'][key] = 'BLOB'
        for key in self.oneturn_sixtrack_input['temp']:
            self.tables['templates'][key] = 'BLOB'
        for key in self.sixtrack_input['temp']:
            self.tables['templates'][key] = 'BLOB'

        for key in self.paths.keys():
            self.tables['env'][key] = 'TEXT'

        for key in self.boinc_vars.keys():
            self.tables['boinc_vars'][key] = 'TEXT'

    def structure(self):
        '''Structure the workspace of this study.
        Prepare the input and output folders.
        Copy the required template files.
        Initialize the database with the defined tables.'''

        temp = self.paths["templates"]
        if not os.path.isdir(temp) or not os.listdir(temp):
            if not os.path.exists(temp):
                os.makedirs(temp)
            app_path = StudyFactory.app_path()
            tem_path = os.path.join(app_path, 'templates')
            print(tem_path)
            if os.path.isdir(tem_path) and os.listdir(tem_path):
                for item in os.listdir(tem_path):
                    s = os.path.join(tem_path, item)
                    d = os.path.join(temp, item)
                    if os.path.isfile(s):
                        shutil.copy2(s, d)
                print("Copy templates from default source templates folder!")
            else:
                print("The default source templates folder %s is inavlid!"%tem_path)
                sys.exit(1)

        if not os.path.isdir(self.paths["madx_in"]):
            os.makedirs(self.paths["madx_in"])
        if not os.path.isdir(self.paths["madx_out"]):
            os.makedirs(self.paths["madx_out"])
        if not os.path.isdir(self.paths["sixtrack_in"]):
            os.makedirs(self.paths["sixtrack_in"])
        if not os.path.isdir(self.paths["sixtrack_out"]):
            os.makedirs(self.paths["sixtrack_out"])
        if not os.path.isdir(self.paths["gather"]):
            os.makedirs(self.paths["gather"])

        #Initialize the database
        dbname = os.path.join(self.study_path, self.dbname)
        self.db = SixDB(dbname, self.db_settings, True)
        self.db.create_tables(self.tables, self.table_keys)

        cont = os.listdir(temp)
        require = []
        require += self.oneturn_sixtrack_input["temp"]
        require.append(self.madx_input["mask_file"])
        for re in require:
            if re not in cont:
                print("The required file %s isn't found in %s!"%(re, temp))
                sys.exit(1)
        outputs = self.db.select('templates', self.tables['templates'].keys())
        if not outputs:
            tab = {}
            for key,value in self.madx_input.items():
                value = os.path.join(self.study_path, value)
                tab[key] = utils.evlt(utils.compress_buf, [value])
            for key in self.oneturn_sixtrack_input['temp']:
                value = os.path.join(self.study_path, key)
                tab[key] = utils.evlt(utils.compress_buf, [value])
            for key in self.sixtrack_input['temp']:
                value = os.path.join(self.study_path, key)
                tab[key] = utils.evlt(utils.compress_buf, [value])
            self.db.insert('templates', tab)
        outputs = self.db.select('env', self.paths.keys())
        if not outputs:
            self.db.insert('env', self.paths)
        outputs = self.db.select('boinc_vars', self.boinc_vars.keys())
        if not outputs:
            self.db.insert('boinc_vars', self.boinc_vars)
        print("All required files are ready!")

    def info(self):
        '''Print the status information of this study'''
        loc = self.study_path
        conts = os.listdir(loc)
        if self.dbname not in conts:
            print("This study directory is empty!")
        else:
            dbname = os.path.join(loc, self.dbname)
            db = SixDB(dbname, self.db_settings)
            mad6t_task = db.select('mad6t_wu', ['job_name', 'status'])
            print('madx and one turn sixtrack jobs:')
            for i in mad6t_task:
                print(i)
            six = db.select('sixtrack_wu', ['job_name', 'status'])
            print('Sixtrack jobs:')
            for j in six:
                print(j)
            db.close()

    def submit_sixtrack(self, **args):
        '''Sumbit the sixtrack jobs to htctondor. p.s. Now we test locally'''
        if 'place' in args:
            execution_field = args['place']
        else:
            execution_field = 'temp'
        execution_field = os.path.abspath(execution_field)
        if not os.path.isdir(execution_field):
            os.makedirs(execution_field)
        if os.listdir(execution_field):
            print("Caution! The folder %s is not empty!"%execution_field)
        cur_path = os.getcwd()
        os.chdir(execution_field)
        for i in self.sixtrack_joblist:
            print("The sixtrack job %s is running...."%i)
            sixtrack.run(i)
        print("All sxitrack jobs are completed normally!")
        os.chdir(cur_path)

    def collect_sixtrack(self):
        '''Collect the results of sixtrack jobs'''
        six_out = self.paths['sixtrack_out']
        job_table = {}
        if os.path.isdir(six_out) and os.listdir(six_out):
            for item in os.listdir(six_out):
                item = os.path.join(six_out, item)
                if os.path.isdir(item) and os.listdir(item):
                    for conts in os.listdir(item):
                        conts = os.path.join(item, conts)
                        if os.path.isdir(conts) and os.listdir(conts):
                            results = os.listdir(conts)
                            for res in self.sixtrack_output:
                                a = [s for s in results if res in s]
                                if a:
                                    a = os.path.join(conts, a[0])
                                else:
                                    print("The result %s isn't found!"%res)

    def prepare_sixtrack_input(self, server='htcondor'):
        '''Prepare the input files for sixtrack job'''
        self.config.clear()
        self.config['sixtrack'] = {}
        six_sec = self.config['sixtrack']
        six_sec['source_path'] = self.paths['templates']
        six_sec['sixtrack_exe'] = self.paths['sixtrack_exe']
        inp = self.sixtrack_input['input']
        six_sec['input_files']= utils.evlt(utils.encode_strings, [inp])
        six_sec['boinc_dir'] = self.paths['boinc_spool']
        if server.lower() == 'htcondor':
            six_sec['boinc'] = 'false'
        elif server.lower() == 'boinc':
            six_sec['boinc'] = 'true'
        else:
            print("Unsupported platform!")
            sys.exit(1)
        inp = self.sixtrack_input['temp']
        six_sec['temp_files'] = utils.evlt(utils.encode_strings, [inp])
        inp = self.sixtrack_output
        six_sec['output_files'] = utils.evlt(utils.encode_strings, [inp])

        self.config['fort3'] = {}
        fort3_sec = self.config['fort3']
        keys = sorted(self.madx_params.keys())
        madx_vals = self.db.select('mad6t_wu', keys, where="task_status='complete'")
        for element in madx_vals:
            for i in range(len(element)):
                ky = keys[i]
                vl = element[i]
                fort3_sec[ky] = str(vl)
        madx_namevsid = self.db.select('mad6t_wu', ['job_name', 'rowid'], where="task_status='complete'")
        [madx_jobnames,jobid] = zip(*madx_namevsid)
        cols = list(self.sixtrack_input['input'].values())
        task_table = {}
        for item in madx_jobnames:
            task_table['mad6t_name'] = item
            item_path = os.path.join(self.paths['sixtrack_in'], item)
            if not os.path.isdir(item_path):
                os.makedirs(item_path)
            s_keys = sorted(self.sixtrack_params.keys())
            values = []
            keys = []
            for key in s_keys:
                val = self.sixtrack_params[key]
                if isinstance(val, list):
                    keys.append(key)
                    s_keys.remove(key)
                    values.append(val)
                else:
                    fort3_sec[key] = str(val)
                    task_table[key] = val
            for element in itertools.product(*values):
                for i in range(len(element)):
                    ky = keys[i]
                    vl = element[i]
                    fort3_sec[ky] = str(vl)
                    task_table[ky] = val
                job_name = self.name_conven('', keys, element, '')
                task_table['sixtrack_name'] = item + job_name
                input_path = os.path.join(item_path, job_name)
                dest_path = os.path.join(self.paths['sixtrack_out'], item, job_name)
                if not os.path.isdir(input_path):
                    os.makedirs(input_path)
                six_sec['input_path'] = input_path
                six_sec['dest_path'] = dest_path
                where = "job_name='%s'"%(item)
                madx_outs = self.db.select('mad6t_task', cols, where)
                num = len(cols)
                for i in range(num):
                    out = madx_outs[0][i]
                    filename = os.path.join(input_path, cols[i])
                    utils.evlt(utils.decompress_buf, [out, filename])
                self.config['boinc'] = self.boinc_vars
                input_name = 'test.ini'
                output = os.path.join(input_path, input_name)
                with open(output, 'w') as f_out:
                    self.config.write(f_out)
                print('Successfully generate input file %s'%output)
                self.sixtrack_joblist.append(output)
                task_table['input_file'] = utils.evlt(utils.compress_buf, [output])
                task_table['task_status'] = 'incomplete'
                task_table['mtime'] = time.time()
                try:
                    self.db.insert('sixtrack_task', task_table)
                except:
                    print("Fail to insert sixtrack task!")

    def submit_mad6t(self, platform='local', **args):
        '''Submit the jobs to cluster or run locally'''
        clean = False
        if platform == 'local':
            if 'place' in args:
                execution_field = args['place']
            else:
                execution_field = 'temp'
            execution_field = os.path.abspath(execution_field)
            if not os.path.isdir(execution_field):
                os.makedirs(execution_field)
            if os.listdir(execution_field):
                clean = False
                print("Caution! The folder %s is not empty!"%execution_field)
            cur_path = os.getcwd()
            os.chdir(execution_field)
            if 'clean' in args:
                clean = args['clean']
            subdb = os.path.join(self.paths['madx_in'], 'sub.db')
            run_status = mad6t_oneturn.run(1, subdb)
            print("The job is running...")
            os.chdir(cur_path)
            if clean:
                shutil.rmtree(execution_field)
        elif platform.lower() == 'htcondor':
            sub = os.path.join(self.paths['madx_in'], 'htcondor_run.sub')
            cmd = 'condor_submit %s'%sub
            os.system(cmd)
        else:
            print("Invlid platfrom!")

    def collect_mad6t_results(self, plat='local', clean='False'):
        '''Collect the results of madx and oneturn sixtrack job and store in
        database
        '''
        self.config.clear()
        self.config['info'] = {}
        info_sec = self.config['info']
        self.config['db_setting'] = self.db_settings

        info_sec['db'] = os.path.join(self.study_path, self.dbname)
        info_sec['path'] = self.paths['madx_out']
        info_sec['outs'] = utils.evlt(utils.encode_strings, [self.madx_output])
        info_sec['clean'] = clean
        task_input = os.path.join(self.paths['gather'], 'mad6t.ini')
        task_index = os.path.join(self.paths['gather'], 'mad6t.list')
        sub_temp = os.path.join(self.paths['templates'], self.htc_temp)
        task_sub = os.path.join(self.paths['gather'], 'htcondor_run.sub')
        with open(task_input, 'w') as f_out:
            self.config.write(f_out)
        with open(task_index, 'w') as f_out:
            f_out.write('0')
        if plat is 'local':
            gather.run(0, task_input)
        elif plat is 'htcondor':
            info = {}
            app_path = StudyFactory.app_path()
            info['%exe'] = os.path.join(app_path, 'lib', 'gather.py')
            info['%input'] = 'mad6t.ini'
            info['%joblist'] = task_index
            info['%dirname'] = self.paths['gather']
            path = os.path.join(self.paths['gather'], '0')
            if not os.path.isdir(path):
                os.makedirs(path)
            tran_input =[]
            tran_input.append(os.path.join(app_path, 'lib', 'utils.py'))
            tran_input.append(os.path.join(app_path, 'lib', 'pysixdb.py'))
            tran_input.append(os.path.join(app_path, 'lib', 'dbadaptor.py'))
            tran_input.append(task_input)
            info['%func'] = utils.evlt(utils.encode_strings, [tran_input])
            with open(sub_temp, 'r') as f_in:
                with open(task_sub, 'w') as f_out:
                    conts = f_in.read()
                    for key, value in info.items():
                        conts = conts.replace(key, value)
                    f_out.write(conts)
            command = 'condor_submit %s'%task_sub
            os.system(command)

    def prepare_madx_single_db(self):
        '''Prepare the input database for madx and one turn sixtrack job'''
        keys = sorted(self.madx_params.keys())
        values = []
        for key in keys:
            values.append(self.madx_params[key])

        check_params = self.db.select('mad6t_wu', list(keys))
        check_jobs = self.db.select('mad6t_wu', ['wu_id','job_name','status'])

        wu_id = len(check_jobs)
        for element in itertools.product(*values):
            madx_table = collections.OrderedDict()
            if element in check_params:
                i = check_params.index(element)
                name = check_jobs[i][1]
                print("The job %s is already in data.db!"%name)
                continue
            for i in range(len(element)):
                ky = keys[i]
                vl = element[i]
                madx_table[ky] = vl
            prefix = self.madx_input['mask_file'].split('.')[0]
            job_name = self.name_conven(prefix, keys, element, '')
            wu_id +=1
            madx_table['wu_id'] = wu_id
            madx_table['status'] = 'incomplete'
            madx_table['job_name'] = job_name
            madx_table['mtime'] = time.time()
            self.db.insert('mad6t_wu', madx_table)
            #self.mad6t_joblist.append(job_name)
            print('Store new job %s into database!'%job_name)
        self.db.insert('oneturn_sixtrack_wu', self.oneturn_sixtrack_params)
        sub_name = os.path.join(self.paths['madx_in'], 'sub.db')
        dbname = os.path.join(self.study_path, self.dbname)
        shutil.copy2(dbname, sub_name)
        sub_db = SixDB(sub_name, self.db_settings)
        sub_db.drop_table('result')
        sub_db.drop_table('sixtrack_wu')
        sub_db.drop_table('sixtrack_task')
        sub_db.drop_table('boinc_vars')
        sub_db.drop_table('mad6t_task')
        where = "status='complete'"
        sub_db.remove('mad6t_wu', where)#remove the completed jobs
        wu_ids = sub_db.select('mad6t_wu', ['wu_id'])
        job_list = os.path.join(self.paths['madx_in'], 'job_id.list')
        with open(job_list, 'w') as f_out:
            for i in wu_ids:
                f_out.write(str(i[0]))
                f_out.write('\n')
        sub_db.close()
        print("The submitted database %s is ready!"%sub_name)

    def prepare_madx_single_input(self):
        '''Prepare the input files for madx and one turn sixtrack job'''
        self.config.clear()
        self.config['madx'] = {}
        madx_sec = self.config['madx']
        self.config['mask'] = {}
        mask_sec = self.config['mask']
        self.config['sixtrack'] = {}
        six_sec = self.config['sixtrack']
        madx_sec['source_path'] = self.paths['templates']
        madx_sec['madx_exe'] = self.paths['madx_exe']
        madx_sec['mask_file'] = self.madx_input["mask_file"]
        inp = self.madx_output
        madx_sec['output_files'] = utils.evlt(utils.encode_strings, [inp])
        six_sec['source_path'] = self.paths['templates']
        six_sec['sixtrack_exe'] = self.paths['sixtrack_exe']
        inp = self.oneturn_sixtrack_input['temp']
        six_sec['temp_files'] = utils.evlt(utils.encode_strings, [inp])
        inp = self.oneturn_sixtrack_input['input']
        six_sec['input_files'] = utils.evlt(utils.encode_strings, [inp])
        inp = self.oneturn_sixtrack_output
        six_sec['output_files'] = utils.evlt(utils.encode_strings, [inp])
        self.config['fort3'] = self.oneturn_sixtrack_params

        keys = sorted(self.madx_params.keys())
        values = []
        for key in keys:
            values.append(self.madx_params[key])

        check_params = self.db.select('mad6t_wu', list(keys))
        check_jobs = self.db.select('mad6t_wu', ['wu_id','job_name','status'])

        wu_id = len(check_params)
        for element in itertools.product(*values):
            madx_table = collections.OrderedDict()
            if element in check_params:
                i = check_params.index(element)
                name = check_jobs[i][1]
                print("The job %s is already in data.db!"%name)
                continue
            for i in range(len(element)):
                ky = keys[i]
                vl = element[i]
                mask_sec[ky] = str(vl)
                madx_table[ky] = vl
            prefix = self.madx_input['mask_file'].split('.')[0]
            job_name = self.name_conven(prefix, keys, element, '')
            mad6t_input = self.paths['madx_in']
            wu_id +=1
            madx_table['wu_id'] = wu_id
            n = str(wu_id)
            madx_sec['dest_path'] = os.path.join(self.paths['madx_out'], n)
            six_sec['dest_path'] = os.path.join(self.paths['madx_out'], n)
            f_out = io.StringIO()
            self.config.write(f_out)
            out = f_out.getvalue()
            madx_table['input_file'] = utils.evlt(utils.compress_buf, [out,'str'])
            madx_table['status'] = 'incomplete'
            madx_table['job_name'] = job_name
            madx_table['mtime'] = time.time()
            self.db.insert('mad6t_wu', madx_table)
            #self.mad6t_joblist.append(job_name)
            print('Store job %s into database!'%job_name)

        #dbname = os.path.join(self.study_path, self.dbname)
        #shutil.copy2(dbname, sub_name)
        #sub_db.drop_table('result')
        #sub_db.drop_table('sixtrack_wu')
        #sub_db.drop_table('sixtrack_task')
        #sub_db.drop_table('boinc_vars')
        #sub_db.drop_table('mad6t_task')
        #where = "status='complete'"
        #sub_db.remove('mad6t_wu', where)#remove the completed jobs
        where = "status='incomplete'"
        outputs = self.db.select('mad6t_wu', ['wu_id', 'input_file'], where)
        if not outputs:
            print("There isn't incomplete job!")
        else:
            sub_name = os.path.join(self.paths['madx_in'], 'sub.db')
            if os.path.exists(sub_name):
                os.remove(sub_name)#remove the old one
            sub_db = SixDB(sub_name, self.db_settings, create=True)
            sub_db.create_table('mad6t_wu', {'wu_id':'int','input_file':'blob'})
            incom_job = {}
            outputs = list(zip(*outputs))
            incom_job['wu_id'] = outputs[0]
            incom_job['input_file'] = outputs[1]
            sub_db.insertm('mad6t_wu', incom_job)
            wu_ids = sub_db.select('mad6t_wu', ['wu_id'])
            job_list = os.path.join(self.paths['madx_in'], 'job_id.list')
            if os.path.exists(job_list):
                os.remove(job_list)
            with open(job_list, 'w') as f_out:
                for i in wu_ids:
                    f_out.write(str(i[0]))
                    f_out.write('\n')
                    out_f = os.path.join(self.paths['madx_out'], str(i[0]))
                    if not os.path.isdir(out_f):
                        os.makedirs(out_f)
            sub_db.close()
            print("The submitted database %s is ready!"%sub_name)
            sub_temp = os.path.join(self.paths['templates'], self.htc_temp)
            sub_file = os.path.join(self.paths['madx_in'], self.htc_temp)
            if os.path.exists(sub_file):
                os.remove(sub_file)#remove the old one
            rep = {}
            app_path = StudyFactory.app_path()
            tran_input =[]
            tran_input.append(os.path.join(app_path, 'lib', 'utils.py'))
            tran_input.append(os.path.join(app_path, 'lib', 'pysixdb.py'))
            tran_input.append(os.path.join(app_path, 'lib', 'dbadaptor.py'))
            tran_input.append(sub_name)
            rep['%func'] = utils.evlt(utils.encode_strings, [tran_input])
            rep['%exe'] = os.path.join(app_path, 'lib', 'mad6t_oneturn.py')
            rep['%dirname'] = self.paths['madx_out']
            rep['%joblist'] = job_list
            rep['%input'] = 'sub.db'
            with open(sub_temp, 'r') as f_in:
                with open(sub_file, 'w') as f_out:
                    conts = f_in.read()
                    for key, value in rep.items():
                        conts = conts.replace(key, value)
                    f_out.write(conts)
            print("The htcondor description file is ready!")

    def name_conven(self, prefix, keys, values, suffix=''):
        '''The convention for naming input file'''
        lStatus = True
        b = ''
        if len(keys) == len(values):
            a = ['_'.join(map(str, i)) for i in zip(keys, values)]
            b = '_'.join(map(str, a))
        else:
            print("The input list keys and values must have same length!")
            lStatus = False
        mk = prefix + '_' + b + suffix
        return mk

class StudyFactory(object):

    def __init__(self, workspace='./sandbox'):
        self.ws = os.path.abspath(workspace)
        self.studies = []
        self._setup_ws()

    def _setup_ws(self):
        '''Setup a workspace'''
        if not os.path.isdir(self.ws):
            os.mkdir(self.ws)
            print('Create new workspace %s!'%self.ws)
        else:
            print('The workspace %s already exists!'%self.ws)
        studies = os.path.join(self.ws, 'studies')
        if not os.path.isdir(studies):
            os.mkdir(studies)
        else:
            self._load()
            self.info()
        templates = os.path.join(self.ws, 'templates')
        if not os.path.isdir(templates):
            os.mkdir(templates)

        app_path = StudyFactory.app_path()
        tem_path = os.path.join(app_path, 'templates')
        contents = os.listdir(templates)
        if not contents:
            if os.path.isdir(tem_path) and os.listdir(tem_path):
                 for item in os.listdir(tem_path):
                     s = os.path.join(tem_path, item)
                     d = os.path.join(templates, item)
                     if os.path.isfile(s):
                         shutil.copy2(s, d)
            else:
                print("The templates folder %s is invalid!"%tem_path)

    def _load(self):
        '''Load the information from an exist workspace!'''
        studies = os.path.join(self.ws, 'studies')
        for item in os.listdir(studies):
            item_path = os.path.join(studies, item)
            if os.path.isdir(item_path):
                self.studies.append(item)

    def info(self):
        '''Print all the studies in the current workspace'''
        print(self.studies)
        return self.studies

    def prepare_study(self, name = ''):
        '''Prepare the config and temp files for a study'''
        studies = os.path.join(self.ws, 'studies')
        if len(name) == 0:
            i = len(self.studies)
            study_name = 'study_%03i'%(i)
        else:
            study_name = name

        study = os.path.join(studies, study_name)
        app_path = StudyFactory.app_path()
        config_temp = os.path.join(app_path, 'lib', 'config.py')
        if not os.path.isdir(study):
            os.makedirs(study)

        tem_path = os.path.join(self.ws, 'templates')
        if os.path.isdir(tem_path) and os.listdir(tem_path):
             for item in os.listdir(tem_path):
                 s = os.path.join(tem_path, item)
                 d = os.path.join(study, item)
                 if os.path.isfile(s):
                     shutil.copy2(s, d)
        else:
            print("Invalid templates folder!")
            sys.exit(1)

    def new_study(self, name, module_path=None, classname='MyStudy'):
        '''Create a new study with a prepared study path'''
        loc = os.path.join(self.ws, 'studies')
        study = os.path.join(loc, name)
        if os.path.isdir(study):
            if module_path is None:
                module_path = os.path.join(study, 'config.py')

            if os.path.isfile(module_path):
                self.studies.append(study)
                module_name = os.path.abspath(module_path)
                module_name = module_name.replace('.py', '')
                mod = SourceFileLoader(module_name, module_path).load_module()
                cls = getattr(mod, classname)
                print("Create a study instance %s"%study)
                return cls(name, loc)
            else:
                print("The configure file 'config.py' isn't found!")
                sys.exit(1)
        else:
            print("Invalid study path! The study path should be initialized at first!")

    @staticmethod
    def app_path():
        '''Get the absolute path of the home directory of pysixdesk'''
        app_path = os.path.abspath(inspect.getfile(Study))
        app_path = os.path.dirname(os.path.dirname(app_path))
        return app_path

