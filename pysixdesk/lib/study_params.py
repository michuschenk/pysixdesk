import re
import os
import logging
from collections import OrderedDict
from itertools import product

from . import machineparams
from .constants import PROTON_MASS
from .utils import PYSIXDESK_ABSPATH, merge_dicts


class StudyParams:
    '''
    Looks for any placeholders in the provided paths and extracts the
    placeholder assigns values from the machine_defaults parameters and the
    f3_defaults attribute. If no default values found, use None.
    This class implements __setitem__ and __getitem__ so the user can interact
    with the StudyParams object similarly to a dict.

    To get the placeholder patterns for the mask file use self.madx.
    To get the placeholder patterns for the oneturn sixtrack job use
    self.oneturn.
    To get the placeholder patterns for the fort.3 file use self.sixtrack.
    '''

    def __init__(self, mask_path,
                 fort_path=os.path.join(PYSIXDESK_ABSPATH, 'templates/fort.3'),
                 machine_defaults=machineparams.HLLHC['col']):
        """
        Args:
            mask_path (str): path to the mask file
            fort_path (str): path to the fort file
            machine_defaults (dict): dictionary containing the default
            parameters of the desired machine/configuration.
        """
        self._logger = logging.getLogger(__name__)
        # comment regexp
        self._reg_comment = re.compile(r'^(\s?!|\s?/).*', re.MULTILINE)
        # placeholder pattern regexp
        self._reg = re.compile(r'%(?!FILE|%)([a-zA-Z0-9_]+/?)')
        self.fort_path = fort_path
        self.mask_path = mask_path
        # initialize empty calculation queue
        self.calc_queue = []
        # TODO: Figure out how to nicely handle the 'chrom_eps' and 'CHROM'
        # parameters, they are not substituting any placeholders, they are only
        # used in the preprocessing job to do some calculations for the
        # oneturnresult file. They shouldn't really be included in the
        # f3_defaults dict, as they are not values for placeholders in fort.3.

        # default parameters for sixtrack/fort.3 specific placeholders
        self.f3_defaults = dict([
                                ("ax0s", 0.1),
                                ("ax1s", 0.1),
                                ("chrom_eps", 0.000001),  # this is not a placeholder
                                ("CHROM", 0),  # this is not a placeholder
                                ("dp1", 0.000001),
                                ("dp2", 0.000001),
                                ("EI", 3.5),
                                ("turnss", 1e5),
                                ("ibtype", 0),
                                ("iclo6", 2),
                                ("idfor", 0),
                                ("imc", 1),
                                ("ilin", 1),
                                ("ition", 0),
                                ("length", 26658.864),
                                ("ndafi", 1),
                                ("nss", 60),  # should this be 60? 30?
                                ("pmass", PROTON_MASS),
                                ("Runnam", 'FirstTurn'),
                                ("ratios", 1),
                                # these toggle_* aren't very pretty.
                                ("toggle_post/", ''),  # '' --> on, '/' --> off
                                ("toggle_diff/", '/'),  # '' --> on, '/' --> off
                                ("toggle_coll/", ''),  # '' --> off, '/' --> on
                                ("writebins", 1),
                                ])
        self.machine_defaults = machine_defaults
        self.defaults = merge_dicts(self.f3_defaults, self.machine_defaults)
        # phasespace params
        # TODO: find sensible defaults
        amp = [8, 10, 12]  # The amplitude
        self.phasespace = dict([
                               ('amp', list(zip(amp, amp[1:]))),
                               ('kang', list(range(1, 1 + 1))),
                               ('kmax', 5),
                               ])

        self.madx = self.find_patterns(self.mask_path)
        self.sixtrack = self.find_patterns(self.fort_path,
                                           mandatory=['chrom_eps', 'CHROM'])

    @property
    def oneturn(self):
        sixtrack = self.sixtrack.copy()
        sixtrack['turnss'] = 1
        sixtrack['nss'] = 1
        sixtrack['Runnam'] = 'FirstTurn'
        return sixtrack

    def keys(self):
        """Gets the keys of `self.madx`, `self.sixtrack` and `self.phasespace`

        Returns:
            list: list of keys.
        """
        return (list(self.madx.keys()) +
                list(self.sixtrack.keys()) +
                list(self.phasespace.keys()))

    def _extract_patterns(self, file):
        '''
        Extracts the patterns from a file.

        Args:
            file (str): path to the file from which to extract the placeholder
            patterns.
        Returns:
            list: list containing the regexp matches, i.e. the placeholders
        '''
        with open(file) as f:
            lines = f.read()
        lines_no_comments = re.sub(self._reg_comment, '', lines)
        matches = re.findall(self._reg, lines_no_comments)
        return matches

    def find_patterns(self, file_path, folder=False, keep_none=True,
                      mandatory=None):
        '''
        Reads file at `file_path` and populates a dict with the matched
        patterns and values taken from `self.defaults`.

        Args:
            file_path (str): path to file to extract placeholder patterns
            folder (bool, optional): if True, check for placeholder patterns
            in all files in the `file_path` fodler.
            keep_none (bool, optional): if True, keeps the None entries in the
            output dict.
            mandatory (list, optional): if provided will add the keys in the
            provided list to the output dict, regardless is they are found in
            the file.

        Returns:
            OrderedDict: dictionnary of the extracted placeholder patterns with
            their values set the entry on `self.defaults`.
        '''
        dirname = os.path.dirname(file_path)
        if folder and dirname != '':
            # extract the patterns for all the files in the directory of the
            # maskfile
            matches = []
            for file in os.listdir(dirname):
                matches += self._extract_patterns(os.path.join(dirname,
                                                               file))
        else:
            matches = self._extract_patterns(file_path)

        out = OrderedDict()
        for ph in matches:
            if ph in self.defaults.keys():
                out[ph] = self.defaults[ph]
            elif keep_none:
                out[ph] = None
        if mandatory is not None:
            for k in mandatory:
                out[k] = self.defaults[k]

        self._logger.debug(f'Found {len(matches)} placeholders in {file_path}.')
        self._logger.debug(f'With {len(set(matches))} unique placeholders.')
        for k, v in out.items():
            self._logger.debug(f'{k}: {v}')
        return out

    def calc(self, get_val_db=None, require=None, **kwargs):
        '''
        Runs the queued calculations, in order.**kwargs are passed
        to the queued function at run time. The output of the queue is put
        in self.sixtrack, and a dictionnary containing the calculation results
        is returned.

        Args:
            get_val_db (SixDB, optional): SixDB object to fecth values from db
            in for the calculations.
            require (list, str optional): If 'all' will run all function in
            calculation queue.
            If None, will run all calculations which don't require any
            database.
            If list of table names, will run calculations whose 'require'
            attribute's keys are a subset of the provided list.
            whose "requires" attribute dict's keys
            **kwargs: passed to the `fun` in the queued calculations

        Returns:
            dict: results of calculation queue.

        Raises:
            ValueError: If the number of output values of a function does not
            match the number of output keys.
        '''

        if require == 'all':
            # all the functions
            queue = self.calc_queue
        elif require is None:
            # the functions which don't require db
            queue = [f for f in self.calc_queue if not hasattr(self.calc_queue,
                                                               'require')]
        else:
            queue = self._filter_queue(require)

        out_dict = {}
        for fun in queue:
            # get the input values with __getitem__
            inp = [self.__getitem__(k) for k in getattr(fun, 'input_keys', [])]
            inp = [[i] if not isinstance(i, list) else i for i in inp]
            # get the values in the function 'require' attribute from
            # the database.
            required = self._get_required_values(get_val_db, fun)
            # cartesian product of dict of lists --> list of dicts
            required = list(self._product_dict(**required))
            # add any kwargs
            [r.update(kwargs) for r in required]
            # add kwarg dicts to the inp list
            inp.append(required)
            # run calculations
            out = []
            for inputs in product(*inp):
                o = fun(*inputs[:-1], **inputs[-1])
                if not isinstance(o, tuple):
                    o = [o]
                if len(o) != len(fun.output_keys):
                    content = (f'The number of outputs of "{fun.__name__}" does'
                               ' not match the number of keys in '
                               f'"{fun.output_keys}".')
                    raise ValueError(content)
                out.append(o)
            # convert columns to list of lists
            out = zip(*out)
            o_dict = {}
            for k, v in zip(fun.output_keys, out):
                self._logger.debug(f'Inserting "{k}": {v}')
                o_dict[k] = v[0] if len(v) == 1 else list(v)
            # update sixtrack as we go, so that calculations which depend on
            # the output of other calcs have their inputs.
            self.sixtrack.update(o_dict)
            # update output dict
            out_dict.update(o_dict)

        # remove complete calculations
        self.calc_queue = [f for f in self.calc_queue if f not in queue]
        return out_dict

    def _product_dict(self, **kwargs):
        '''
        Cartesian product of dict of lists.
        From:
        https://stackoverflow.com/questions/5228158/cartesian-product-of-a-dictionary-of-lists

        Args:
            inp (dict): dict of lists on which to do the product.

        Returns:
            list : list of dicts.

        Example:
            list(self._product_dict(**{"number": [1,2,3],
                                       "color": ["orange","blue"]}))
            >>[{"number": 1, "color": "orange"},
               {"number": 1, "color": "blue"},
               {"number": 2, "color": "orange"},
               {"number": 2, "color": "blue"},
               {"number": 3, "color": "orange"},
               {"number": 3, "color": "blue"}]
        '''
        keys = kwargs.keys()
        vals = kwargs.values()
        for instance in product(*vals):
            yield dict(zip(keys, instance))

    def _filter_queue(self, require):
        '''
        Filters the calculation queue based on the 'require' attribute.

        Args:
            require (list): list of keys which must be contained in the
            'require' attribute dictionnary for the function to be included.

        Returns:
            list: subset of the calculation queue.
        '''
        queue = []
        for f in self.calc_queue:
            # if the required tables are a subset of the require list
            req_table = getattr(f, 'require', None)
            if req_table is not None:
                if set(req_table.keys()).issubset(set(require)):
                    queue.append(f)
        return queue

    def _get_required_values(self, db, fun):
        '''
        Gets the values needed in the dict fun.require from the database.

        Args:
            db (SicDB): Databse from which to extract the values.
            fun (callable): calculation queue function.

        Returns:
            dict: dictionnary containing the values of the required parameters.
        '''
        required = {}
        if hasattr(fun, 'require'):
            for r_table, r_list in fun.require.items():
                if not isinstance(r_list, list):
                    r_list = [r_list]
                r_values = db.select(r_table, r_list)
                # convert columns to list of list
                r_values = zip(*r_values)
                required.update({k: v for k, v in zip(r_list, r_values)})
        return required

    def __repr__(self):
        '''
        Unified __repr__ of the three dictionnaries.
        '''
        return '\n\n'.join(['Madx params: ' + self.madx.__repr__(),
                            'SixTrack params: ' + self.sixtrack.__repr__(),
                            'Phase space params: ' + self.phasespace.__repr__()])

    # set and get items like a dict
    def __setitem__(self, key, val):
        '''
        Adds entry to the appropriate dictionnary(ies) which already contains
        the key.
        '''
        if key not in self.keys():
            raise KeyError(f'"{key}" not in extracted placeholders.')
        if key in self.phasespace.keys():
            self.phasespace[key] = val
        if key in self.madx.keys():
            self.madx[key] = val
        if key in self.sixtrack.keys():
            self.sixtrack[key] = val

    def __getitem__(self, key):
        '''
        Gets entry from the first dictionnary which contains the key.
        '''
        if key not in self.keys():
            raise KeyError(key)
        if key in self.phasespace.keys():
            return self.phasespace[key]
        if key in self.madx.keys():
            return self.madx[key]
        if key in self.sixtrack.keys():
            return self.sixtrack[key]

    @staticmethod
    def _find_none(dic):
        """Finds the keys of any entry in `dic` with a None value.

        Args:
            dic (dict): Dictionnary to check.

        Returns:
            list: list of keys whose value are None.
        """
        out = []
        for k, v in dic.items():
            if v is None:
                out.append(k)
        return out

    def _remove_none(self, dic):
        """Removes Nones in dictionnary `dic`."""
        for k in self._find_none(dic):
            del dic[k]

    def drop_none(self):
        """
        Drop Nones from `self.madx`, `self.sixtrack` and `self.phasespace`.
        """
        self._remove_none(self.madx)
        self._remove_none(self.sixtrack)
        self._remove_none(self.phasespace)


def set_property(key, value):
    '''
    Simple decorator to add attributes to functions.
    '''
    def decorated_func(func):
        setattr(func, key, value)
        return func
    return decorated_func
