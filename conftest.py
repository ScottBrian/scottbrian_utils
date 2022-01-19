from doctest import ELLIPSIS
from doctest import OutputChecker as BaseOutputChecker
from sybil import Sybil
from sybil.example import Example  # sbt
from sybil.parsers.capture import parse_captures
from sybil.parsers.codeblock import PythonCodeBlockParser
from sybil.parsers.doctest import DocTestParser
from sybil.parsers.doctest import DocTest  # sbt
from scottbrian_utils.time_hdr import get_datetime_match_string
import re

class SbtOutputChecker(BaseOutputChecker):
    def __init__(self):
        self.fix_num = 0

    def check_output(self, want, got, optionflags):
        if self.fix_num == 1:
            diag_msg_dt_fmt = "%H:%M:%S.%f"
            modname_match_str = " <.+>"
            match_str = (get_datetime_match_string(diag_msg_dt_fmt)
                         + modname_match_str)

            replacement = '16:20:05.909260 <input>'
            got = re.sub(match_str, replacement, got)

            match_str = re.escape(r'\prod_files\file1.csv')
            replacement = '/prod_files/file1.csv'
            got = re.sub(match_str, replacement, got)

            match_str = re.escape(r'\test_files\test_file1.csv')
            replacement = '/test_files/test_file1.csv'
            got = re.sub(match_str, replacement, got)

            time_hdr_dt_format = "%a %b %d %Y %H:%M:%S"
            match_str = get_datetime_match_string(time_hdr_dt_format)
            replacement = 'Mon Jun 29 2020 18:22:51'
            got = re.sub(match_str, replacement, got)
            replacement = 'Mon Jun 29 2020 18:22:50'
            got = re.sub(match_str, replacement, got, count=1)

            match_str = 'Elapsed time: 0:00:00       '
            replacement = 'Elapsed time: 0:00:00.001204'
            got = re.sub(match_str, replacement, got)

        return BaseOutputChecker.check_output(self, want, got, optionflags)


class SbtDocTestParser(DocTestParser):
    def __init__(self, optionflags=0):
        DocTestParser.__init__(self, optionflags=optionflags)
        self.runner._checker = SbtOutputChecker()

    def evaluate(self, sybil_example: Example) -> str:
        example = sybil_example.parsed
        namespace = sybil_example.namespace
        output = []
        # original_checker = self.runner._checker
        # if example.lineno == 26:
        if 'README.rst' in sybil_example.path:
            self.runner._checker.fix_num = 1
            # self.runner._checker = SbtOutputChecker()
            # sybil_example.parsed.want = (f"{'sbt_fix_readme'}"
            #                              f"{sybil_example.parsed.want}")
        print(f'{example.lineno=}')  # sbt
        print(f'{type(example.lineno)=}')  # sbt
        print(f'{sybil_example.parsed.source=}')  # sbt
        print(f'{sybil_example.parsed.want=}')  # sbt
        print(f'{sybil_example.path=}')  # sbt
        print(f'{sybil_example.path=}')  # sbt
        # print(f'{self.runner=}')  # sbt
        # print(f'{self.runner._checker=}')  #sbt
        self.runner.run(
            DocTest([example], namespace, name=None,
                    filename=None, lineno=example.lineno, docstring=None),
            clear_globs=False,
            out=output.append
        )
        # self.runner._checker = original_checker
        self.runner._checker.fix_num = 0
        return ''.join(output)


pytest_collect_file = Sybil(
    parsers=[
        SbtDocTestParser(optionflags=ELLIPSIS),
        PythonCodeBlockParser(),
    ],
    # patterns=['*.rst', '*.py'],
    patterns=['*.rst'],
).pytest()
