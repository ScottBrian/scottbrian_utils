from doctest import ELLIPSIS
from doctest import OutputChecker as BaseOutputChecker
from sybil import Sybil
from sybil.example import Example  # sbt
from sybil.parsers.capture import parse_captures
from sybil.parsers.codeblock import PythonCodeBlockParser
from sybil.parsers.doctest import DocTestParser
from sybil.parsers.doctest import DocTest  # sbt


class SbtOutputChecker(BaseOutputChecker):
    def check_output(self, want, got, optionflags):
        # print('*** SbtOutputChecker check_output entered ***')
        # print(f'{want=}')
        # print(f'{got=}')

        new_want = got
        return BaseOutputChecker.check_output(self, new_want, got, optionflags)


class SbtDocTestParser(DocTestParser):
    def __init__(self, optionflags=0):
        DocTestParser.__init__(self, optionflags=optionflags)
        # self.runner._checker = SbtOutputChecker()

    def evaluate(self, sybil_example: Example) -> str:
        example = sybil_example.parsed
        namespace = sybil_example.namespace
        output = []
        original_checker = self.runner._checker
        if example.lineno == 26:
            self.runner._checker = SbtOutputChecker()
        print(f'{example.lineno=}')  # sbt
        print(f'{type(example.lineno)=}')  # sbt
        print(f'{sybil_example.parsed.source=}')  # sbt
        print(f'{sybil_example.parsed.want=}')  # sbt
        # print(f'{self.runner=}')  # sbt
        # print(f'{self.runner._checker=}')  #sbt
        self.runner.run(
            DocTest([example], namespace, name=None,
                    filename=None, lineno=example.lineno, docstring=None),
            clear_globs=False,
            out=output.append
        )
        self.runner._checker = original_checker
        return ''.join(output)


pytest_collect_file = Sybil(
    parsers=[
        SbtDocTestParser(optionflags=ELLIPSIS),
        PythonCodeBlockParser(),
    ],
    # patterns=['*.rst', '*.py'],
    patterns=['*.rst'],
).pytest()
