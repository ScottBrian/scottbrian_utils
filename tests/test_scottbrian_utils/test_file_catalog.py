"""test_file_catalog.py module."""

# standard library imports
import pytest
from typing import Any, List

# third party imports

# local imports
import scottbrian_utils.file_catalog as cat


class TestFileCatalog:
    """TestFileCatalog class."""
    # build case list for tests
    # first tuple item is the file name and second tuple item is the
    # full file path
    case_list = [[('file1', '/run/media/file1.csv')],
                 [('file1', '/run/media/file1.csv'),
                  ('file2', '/run/media/file2.csv')],
                 [('file1', '/run/media/file1.csv'),
                  ('file2', '/run/media/file2.csv'),
                  ('file3', '/run/media/file3.csv')],
                 [('file1', '/run/media/file1.csv'),
                  ('file2', '/run/media/file2.csv'),
                  ('file3', '/run/media/file3.csv'),
                  ('file4', '/run/media/file4.csv')],
                 [('file1', '/run/media/file1.csv'),
                  ('file2', '/run/media/file2.csv'),
                  ('file3', '/run/media/file3.csv'),
                  ('file4', '/run/media/file4.csv'),
                  ('file5', '/run/media/file5.csv')]
                 ]

    def test_file_catalog_with_no_file_specs(self,
                                             capsys: Any) -> None:
        """test_file_catalog with no file_specs not in list.

        Args:
            capsys: instance of the capture sys fixture

        """
        a_catalog = cat.FileCatalog()

        assert len(a_catalog) == 0

        with pytest.raises(cat.FileNameNotFound):
            _ = a_catalog.get_path('file1')

        print(a_catalog)  # test of __repr__
        captured = capsys.readouterr().out

        expected = "FileCatalog()\n"

        assert captured == expected

    def test_file_catalog_with_empty_file_specs(self) -> None:
        """test_file_catalog with empty file_specs."""
        with pytest.raises(cat.FileSpecIncorrect):
            _ = cat.FileCatalog(())  # type: ignore

        with pytest.raises(cat.FileSpecIncorrect):
            _ = cat.FileCatalog([])

        with pytest.raises(cat.FileSpecIncorrect):
            _ = cat.FileCatalog([()])  # type: ignore

        with pytest.raises(cat.FileSpecIncorrect):
            _ = cat.FileCatalog('file1')  # type: ignore

        with pytest.raises(cat.FileSpecIncorrect):
            _ = cat.FileCatalog(('file1'))  # type: ignore

        with pytest.raises(cat.FileSpecIncorrect):
            _ = cat.FileCatalog(['file1'])  # type: ignore

        with pytest.raises(cat.FileSpecIncorrect):
            _ = cat.FileCatalog([('file1')])  # type: ignore

        with pytest.raises(cat.FileSpecIncorrect):
            _ = cat.FileCatalog([(42)])  # type: ignore

        with pytest.raises(cat.FileSpecIncorrect):
            _ = cat.FileCatalog([(42, 24)])  # type: ignore

        with pytest.raises(cat.FileSpecIncorrect):
            _ = cat.FileCatalog([(42, 'path1')])  # type: ignore

        with pytest.raises(cat.FileSpecIncorrect):
            _ = cat.FileCatalog([('file1', 42)])  # type: ignore

        with pytest.raises(cat.FileSpecIncorrect):
            _ = cat.FileCatalog([[('file1', 'path1')]])  # type: ignore

        with pytest.raises(cat.FileSpecIncorrect):
            _ = cat.FileCatalog([(('file1', 'path1'),)])  # type: ignore

    def test_file_catalog_with_single_file_specs(self,
                                                 capsys: Any) -> None:
        """test_file_catalog with single file_specs not in list.

        Args:
            capsys: instance of the capture sys fixture

        """
        file_1 = 'file1'
        path_1 = '/run/media/file1.csv'

        for i in range(9):
            if i == 0:
                a_catalog = cat.FileCatalog(('file1', '/run/media/file1.csv'))

            elif i == 1:
                a_catalog = cat.FileCatalog([('file1',
                                              '/run/media/file1.csv')])

            elif i == 2:
                a_catalog = cat.FileCatalog((file_1, path_1))

            elif i == 3:
                a_catalog = cat.FileCatalog([(file_1, path_1)])

            elif i == 4:
                file_spec4 = ('file1', '/run/media/file1.csv')
                a_catalog = cat.FileCatalog(file_spec4)

            elif i == 5:
                file_spec5 = ('file1', '/run/media/file1.csv')
                a_catalog = cat.FileCatalog([file_spec5])

            elif i == 6:
                file_spec6 = (file_1, path_1)
                a_catalog = cat.FileCatalog(file_spec6)

            elif i == 7:
                file_spec7 = (file_1, path_1)
                a_catalog = cat.FileCatalog([file_spec7])

            else:  # i == 8:
                file_spec8 = [(file_1, path_1)]
                a_catalog = cat.FileCatalog(file_spec8)

            assert len(a_catalog) == 1

            assert a_catalog.get_path('file1') == '/run/media/file1.csv'

            with pytest.raises(cat.FileNameNotFound):
                _ = a_catalog.get_path('file2')

            print(a_catalog)  # test of __repr__
            captured = capsys.readouterr().out

            expected = "FileCatalog(('file1', '/run/media/file1.csv'))\n"

            assert captured == expected

    @pytest.mark.parametrize('file_specs',  # type: ignore
                             case_list)
    def test_file_catalog_with_list_of_file_specs(
            self,
            capsys: Any,
            file_specs: List[cat.FileSpec]) -> None:
        """test_file_catalog with lists of file_specs.

        Args:
            capsys: instance of the capture sys fixture
            file_specs: the list of file names and paths to use

        """
        for j in range(3):
            if j == 0:
                a_catalog = cat.FileCatalog(file_specs)
            elif j == 1:
                a_catalog = cat.FileCatalog()
                a_catalog.add_paths(file_specs)
            else:
                a_catalog = cat.FileCatalog()
                for k, file_spec in enumerate(file_specs):
                    assert len(a_catalog) == k
                    file_name = file_spec[0]
                    full_path = file_spec[1]
                    with pytest.raises(cat.FileNameNotFound):
                        _ = a_catalog.get_path(file_name)

                    a_catalog.add_paths(file_spec)
                    assert a_catalog.get_path(file_name) == full_path
                    assert len(a_catalog) == k+1

            assert len(a_catalog) == len(file_specs)

            num_indent_spaces = len('FileCatalog') + len('([')
            indent_spaces = ''
            parms = ''
            for i, file_spec in enumerate(file_specs):
                file_name = file_spec[0]
                full_path = file_spec[1]
                assert a_catalog.get_path(file_name) == full_path
                if (i < 2) or (i == len(file_specs)-1):  # first 2 or last
                    parms = parms + indent_spaces + "('" \
                        + file_name + "', '" + full_path + "'),\n"
                if (i == 2) and (i != len(file_specs)-1):  # middle, not last
                    parms = parms + indent_spaces + '...\n'
                indent_spaces = ' ' * num_indent_spaces

            parms = parms[:-2]  # remove final comma and new_line

            if len(file_specs) > 1:
                parms = '[' + parms + ']'  # brackets when more than one entry

            expected = 'FileCatalog(' + parms + ')\n'
            print(a_catalog)  # test of __repr__
            captured = capsys.readouterr().out
            assert captured == expected

    @pytest.mark.parametrize('file_specs',  # type: ignore
                             case_list)
    def test_file_catalog_add_paths_exceptions(
            self,
            capsys: Any,
            file_specs: List[cat.FileSpec]) -> None:
        """test_file_catalog add_paths exceptions.

        Args:
            capsys: instance of the capture sys fixture
            file_specs: the list of file names and paths to use

        """
        # instantiate a catalog
        a_catalog = cat.FileCatalog(file_specs)
        assert len(a_catalog) == len(file_specs)

        # try to add the file_specs again - should be OK
        a_catalog.add_paths(file_specs)
        assert len(a_catalog) == len(file_specs)

        for file_spec in file_specs:
            # the number of entries should remain the same throughout tests
            assert len(a_catalog) == len(file_specs)
            file_name = file_spec[0]
            full_path = file_spec[1]

            # we should always find the entries we added earlier
            assert a_catalog.get_path(file_name) == full_path

            # try to add same entry again
            a_catalog.add_paths((file_name, full_path))
            assert len(a_catalog) == len(file_specs)
            assert a_catalog.get_path(file_name) == full_path

            diff_path = 'different/path'

            # should get the exception with same file name but different path

            with pytest.raises(cat.IllegalAddAttempt):
                a_catalog.add_paths((file_name, diff_path))

            # ensure we still have expected results
            assert len(a_catalog) == len(file_specs)
            assert a_catalog.get_path(file_name) == full_path

            # try adding two entries, one good and one bad
            new_file_name = 'newFile1'
            new_file_path = 'newFilePath1'

            with pytest.raises(cat.IllegalAddAttempt):
                a_catalog.add_paths([(new_file_name, new_file_path),
                                     (file_name, diff_path)])

            # ensure we still have expected results
            with pytest.raises(cat.FileNameNotFound):
                _ = a_catalog.get_path(new_file_name)
            assert len(a_catalog) == len(file_specs)
            assert a_catalog.get_path(file_name) == full_path

    @pytest.mark.parametrize('file_specs',  # type: ignore
                             case_list)
    def test_file_catalog_del_paths_with_list_of_file_specs(
            self,
            capsys: Any,
            file_specs: List[cat.FileSpec]) -> None:
        """test_file_catalog delete paths with lists of file_specs.

        Args:
            capsys: instance of the capture sys fixture
            file_specs: the list of file names and paths to use

        """
        expected = 'FileCatalog()\n'  # all cases will expect zero entries

        a_catalog = cat.FileCatalog()  # start with empty catalog
        assert len(a_catalog) == 0
        print(a_catalog)
        assert capsys.readouterr().out == expected

        # attempt to delete paths from empty catalog - should be ok
        a_catalog.del_paths(file_specs)
        assert len(a_catalog) == 0
        print(a_catalog)
        assert capsys.readouterr().out == expected

        # add all paths to catalog
        a_catalog.add_paths(file_specs)
        assert len(a_catalog) == len(file_specs)
        print(a_catalog)
        assert capsys.readouterr().out != expected  # should not be empty

        # delete all paths
        a_catalog.del_paths(file_specs)
        assert len(a_catalog) == 0
        print(a_catalog)
        assert capsys.readouterr().out == expected

        # try doing partial deletes
        a_catalog = cat.FileCatalog()
        for file_spec in file_specs:
            # verify each loop has empty catalog
            assert len(a_catalog) == 0

            file_name = file_spec[0]
            full_path = file_spec[1]

            for i in range(2):
                a_catalog.add_paths(file_spec)
                assert a_catalog.get_path(file_name) == full_path
                assert len(a_catalog) == 1

                if i == 0:
                    a_catalog.del_paths(file_spec)  # delete specific path
                else:
                    a_catalog.del_paths(file_specs)  # delete them all

                assert len(a_catalog) == 0
                with pytest.raises(cat.FileNameNotFound):
                    _ = a_catalog.get_path(file_name)

            for i in range(2):
                a_catalog.add_paths(file_specs)
                assert a_catalog.get_path(file_name) == full_path
                assert len(a_catalog) == len(file_specs)

                if i == 0:
                    a_catalog.del_paths(file_spec)  # delete specific path
                    assert len(a_catalog) == len(file_specs) - 1
                    with pytest.raises(cat.FileNameNotFound):
                        _ = a_catalog.get_path(file_name)
                else:
                    a_catalog.del_paths(file_specs)  # delete them all
                    assert len(a_catalog) == 0
                    with pytest.raises(cat.FileNameNotFound):
                        _ = a_catalog.get_path(file_name)

    @pytest.mark.parametrize('file_specs',  # type: ignore
                             case_list)
    def test_file_catalog_del_paths_exceptions(
            self,
            capsys: Any,
            file_specs: List[cat.FileSpec]) -> None:
        """test_file_catalog add_paths exceptions.

        Args:
            capsys: instance of the capture sys fixture
            file_specs: the list of file names and paths to use

        """
        # instantiate a catalog
        a_catalog = cat.FileCatalog(file_specs)
        assert len(a_catalog) == len(file_specs)

        for file_spec in file_specs:
            # the number of entries should remain the same throughout tests
            assert len(a_catalog) == len(file_specs)
            file_name = file_spec[0]
            full_path = file_spec[1]

            # we should always find the entries we added earlier
            assert a_catalog.get_path(file_name) == full_path

            diff_path = 'different/path'

            # should get del exception with same file name but different path

            with pytest.raises(cat.IllegalDelAttempt):
                a_catalog.del_paths((file_name, diff_path))

            # ensure we still have expected results
            assert len(a_catalog) == len(file_specs)
            assert a_catalog.get_path(file_name) == full_path

            # try deleting two entries, one good and one bad
            with pytest.raises(cat.IllegalDelAttempt):
                a_catalog.del_paths([(file_name, full_path),
                                     (file_name, diff_path)])

            # ensure we still have expected results
            assert len(a_catalog) == len(file_specs)
            assert a_catalog.get_path(file_name) == full_path
