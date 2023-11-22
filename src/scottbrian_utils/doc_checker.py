"""Module doc_checker.

======
DocChecker
======

The DocChecker class is used to help verify the documentation code
examples.
"""
from doctest import OutputChecker as BaseOutputChecker

from sybil.document import Document
from sybil.example import Example
from sybil.evaluators.doctest import DocTestEvaluator, DocTest
from sybil.parsers.abstract import DocTestStringParser
from sybil.region import Region

from typing import Iterable


class DocCheckerOutputChecker(BaseOutputChecker):
    def __init__(self):
        self.mod_name = None
        self.msgs = []

    def check_output(self, want, got, optionflags):
        return BaseOutputChecker.check_output(self, want, got, optionflags)


class DocCheckerTestEvaluator(DocTestEvaluator):
    def __init__(self,
                 doc_checker_output_checker,
                 optionflags=0):
        DocTestEvaluator.__init__(self, optionflags=optionflags)

        # set our checker which will modify the test cases as needed
        # self.runner._checker = DocCheckerOutputChecker()
        self.runner._checker = doc_checker_output_checker

    def __call__(self, sybil_example: Example) -> str:
        example = sybil_example.parsed
        namespace = sybil_example.namespace
        output = []

        # set the mod name for our check_output in DocCheckerOutputChecker
        mod_name = sybil_example.path.rsplit(sep=".", maxsplit=1)[0]
        mod_name = mod_name.rsplit(sep="\\", maxsplit=1)[1]
        self.runner._checker.mod_name = mod_name

        self.runner.run(
            DocTest([example], namespace, name=sybil_example.path,
                    filename=None, lineno=example.lineno, docstring=None),
            clear_globs=False,
            out=output.append
        )
        if self.runner._checker.msgs:
            print(f'{self.runner._checker.msgs=}')
        self.runner._checker.msgs = []
        return ''.join(output)


class DocCheckerTestParser:
    def __init__(self,
                 optionflags=0,
                 doc_checker_output_checker=DocCheckerOutputChecker()):
        self.string_parser = DocTestStringParser(
            DocCheckerTestEvaluator(doc_checker_output_checker, optionflags))

    def __call__(self, document: Document) -> Iterable[Region]:
        return self.string_parser(document.text, document.path)
