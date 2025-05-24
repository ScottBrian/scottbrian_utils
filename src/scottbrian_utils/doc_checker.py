"""Module doc_checker.

==========
DocChecker
==========

The DocChecker class is used to help verify the documentation code
examples. It builds upon Sybil and provides the ability to adjust the
doc examples so that they verify correctly. If, for instance, a code
example involves a timestamp, the expected output written at the time of
the example will fail to match the timestamp generated when the example
is tested. Example 1 below shows a way to make the adjustment to the
timestamp so that it will match.

The DocChecker also has a way to optionally print messages for
troubleshooting cases that fail to verify. This is done by appending to
the msgs variable as shown below in example 1 just before the return
statement.

:Example 1: This example shows how to make an adjustment to accommodate
            doc examples in a module called time_hdr that have
            timestamps in the output. The code needs to replace the
            timestamps in the 'want' variable so that it will match
            the timestamp from running the example at the time of the
            doctest. Place the following code into a conftest.py file in
            the project top directory (see scottbrian-utils for an
            example).

.. code-block:: python

    from doctest import ELLIPSIS
    from doctest import OutputChecker as BaseOutputChecker

    import re

    from sybil import Sybil
    from sybil.parsers.rest import PythonCodeBlockParser

    from scottbrian_utils.time_hdr import get_datetime_match_string
    from scottbrian_utils.doc_checker import DocCheckerTestParser

    from typing import Any

    class SbtDocCheckerOutputChecker(DocCheckerOutputChecker):
        def __init__(self) -> None:
            super().__init__()

        def check_output(self, want, got, optionflags):
            old_want = want
            old_got = got

            def repl_dt(match_obj: Any) -> str:
                return found_items.__next__().group()

            if self.mod_name == 'time_hdr' or self.mod_name == 'README':
                # find the actual occurrences and replace in want
                for time_hdr_dt_format in ["%a %b %d %Y %H:%M:%S",
                                           "%m/%d/%y %H:%M:%S"]:
                    match_str = get_datetime_match_string(
                                    time_hdr_dt_format)

                    match_re = re.compile(match_str)
                    found_items = match_re.finditer(got)
                    want = match_re.sub(repl_dt, want)

                # replace elapsed time in both want and got
                match_str = 'Elapsed time: 0:00:00.[0-9| ]{6,6}'
                replacement = 'Elapsed time: 0:00:00       '
                want = re.sub(match_str, replacement, want)
                got = re.sub(match_str, replacement, got)

            self.msgs.append([old_want, want, old_got, got])
            return super().check_output(want, got, optionflags)


    pytest_collect_file = Sybil(
        parsers=[
            DocCheckerTestParser(optionflags=ELLIPSIS,
                                 doc_checker_output_checker=SbtDocCheckerOutputChecker()
                                 ),
            PythonCodeBlockParser(),],
        patterns=['*.rst', '*.py'],
        ).pytest()

:Example 2: For standard doctest checking with no special cases, place
            the following code into a conftest.py file in the project
            top directory (see scottbrian-locking for an example).

.. code-block:: python

    from doctest import ELLIPSIS

    from sybil import Sybil
    from sybil.parsers.rest import PythonCodeBlockParser

    from scottbrian_utils.doc_checker import DocCheckerTestParser


    pytest_collect_file = Sybil(
        parsers=[
            DocCheckerTestParser(optionflags=ELLIPSIS,
                                 ),
            PythonCodeBlockParser(),],
        patterns=['*.rst', '*.py'],
        ).pytest()

"""

from doctest import OutputChecker as BaseOutputChecker

from sybil.document import Document
from sybil.example import Example
from sybil.evaluators.doctest import DocTestEvaluator, DocTest
from sybil.parsers.abstract import DocTestStringParser
from sybil.region import Region

from typing import Iterable


class DocCheckerOutputChecker(BaseOutputChecker):
    def __init__(self) -> None:
        """Initialize the output checker object."""
        # note that BaseOutputChecker is actually OutputChecker in
        # doctest.py (Sybil imports it as OutputChecker) and
        # OutputChecker has no __init__ method
        self.mod_name: str = ""
        self.msgs: list[str] = []

    def check_output(self, want: str, got: str, optionflags: int) -> bool:
        """Check the output of the example against expected value.

        Args:
            want: the expected value of the example output
            got: the actual value of the example output
            optionflags: doctest option flags for the Sybil
                BaseOutPutChecker check_output method

        Returns:
            True if the want and got values match, False otherwise
        """
        return super().check_output(want, got, optionflags)


class DocCheckerTestEvaluator(DocTestEvaluator):
    def __init__(
        self, doc_checker_output_checker: DocCheckerOutputChecker, optionflags: int = 0
    ) -> None:
        """Initialize the evaluator object.

        Args:
            doc_checker_output_checker: invocation of the output
                check to use
            optionflags: flags passed along to the Sybil
                DocTestEvaluator

        """
        DocTestEvaluator.__init__(self, optionflags=optionflags)

        # set our checker which may modify the test cases as needed
        # self.runner._checker = DocCheckerOutputChecker()
        self.runner._checker = doc_checker_output_checker  # type: ignore

    def __call__(self, sybil_example: Example) -> str:
        """Call method.

        Args:
            sybil_example: the doc example to check

        Returns:
            The string
        """
        example = sybil_example.parsed
        namespace = sybil_example.namespace
        output: list[str] = []

        # set the mod name for our check_output in
        # DocCheckerOutputChecker
        mod_name = sybil_example.path.rsplit(sep=".", maxsplit=1)[0]
        mod_name = mod_name.rsplit(sep="\\", maxsplit=1)[1]
        self.runner._checker.mod_name = mod_name  # type: ignore

        self.runner.run(
            DocTest(
                [example],
                namespace,
                name=sybil_example.path,
                filename=None,
                lineno=example.lineno,
                docstring=None,
            ),
            clear_globs=False,
            out=output.append,
        )
        if self.runner._checker.msgs:  # type: ignore
            print(f"{self.runner._checker.msgs=}")  # type: ignore
        self.runner._checker.msgs = []  # type: ignore
        return "".join(output)


class DocCheckerTestParser:
    def __init__(
        self,
        optionflags: int = 0,
        doc_checker_output_checker: DocCheckerOutputChecker = DocCheckerOutputChecker(),
    ) -> None:
        """Initialize the parser object.

        Args:
            optionflags: flags passed along to the Sybil
                DocTestEvaluator
            doc_checker_output_checker: invocation of the output
                check to use

        """
        self.string_parser = DocTestStringParser(
            DocCheckerTestEvaluator(doc_checker_output_checker, optionflags)
        )

    def __call__(self, document: Document) -> Iterable[Region]:
        """Call method.

        Args:
            document: the document to be tested

        Returns:
            The region is returned
        """
        return self.string_parser(document.text, document.path)
