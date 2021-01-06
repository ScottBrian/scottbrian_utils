"""Module file_catalog.

============
file_catalog
============

With **file_catalog**, you can set up a mapping of file names to
their full path strings. This make it easy to use in an application where the
full paths might be different for various runs, such as between production and
test. This way, you can keep different catalogs for different runs of the
application.

:Example: instantiate production and test catalogs for one file

>>> from scottbrian_utils.file_catalog import FileCatalog
>>> prod_catalog = FileCatalog([('file1', '/run/media/prod_files/file1.csv')])
>>> print(prod_catalog.get_path('file1'))
/run/media/prod_files/file1.csv

>>> test_cat = FileCatalog([('file1', '/run/media/test_files/test_file1.csv')])
>>> print(test_cat.get_path('file1'))
/run/media/test_files/test_file1.csv

The file_catalog module contains:

    1) FileCatalog class with add_paths, del_paths,  and get_path methods
    2) FileSpec type alias that you can use for type hints in your code
    3) Error exception classes:

       a. FileNameNotFound
       b. FileSpecIncorrect
       c. IllegalAddAttempt
       d. IllegalDelAtempt

"""

from typing import Dict, List, Tuple, Type, TYPE_CHECKING, Optional

FileSpec = Tuple[str, str]


class FileCatalogError(Exception):
    """Base class for exception in this module."""
    pass


class FileSpecIncorrect(FileCatalogError):
    """FileCatalog exception for an incorrect file_specs specification."""
    pass


class IllegalAddAttempt(FileCatalogError):
    """FileCatalog exception attempted add of existing but different path."""
    pass


class IllegalDelAttempt(FileCatalogError):
    """FileCatalog exception attempted del of existing but different path."""
    pass


class FileNameNotFound(FileCatalogError):
    """FileNameNotFound exception when the file name is not in the catalog."""
    pass


class FileCatalog:
    """Provides a mapping of file names and full paths.

    This is useful for cases where an application is to be used in various
    environments with files that are in different places. Another use is where
    one set of files is used for normal processing and another set is used for
    testing purposes.
    """

    def __init__(self,
                 # file_specs: Union[None, FileSpec, List[FileSpec]] = None
                 file_specs: Optional[List[FileSpec]] = None
                 ) -> None:
        """Store the input file specs to a data frame.

        Args:
            file_specs: A set of tuples with each tuple having two items.
                          The first item is the file name, and the second
                          item is the full path to the file

        :Example: instantiate a catalog with two files

        >>> from scottbrian_utils.file_catalog import FileCatalog
        >>> a_catalog = FileCatalog([('file1', '/run/media/file1.csv'),
        ...                          ('file2', '/run/media/file2.pdf')])
        >>> print(a_catalog.get_path('file2'))
        /run/media/file2.pdf

        """
        self.catalog: Dict[str, str] = {}
        if file_specs is not None:
            self.add_paths(file_specs)

    def __len__(self) -> int:
        """Return the number of items in the catalog.

        Returns:
            The number of entries in the catalog as an integer

        :Example: instantiate a catalog with three files

        >>> from scottbrian_utils.file_catalog import FileCatalog
        >>> a_catalog = FileCatalog([('file1', '/run/media/file1.csv'),
        ...                          ('file2', '/run/media/file2.pdf'),
        ...                          ('file5', '/run/media/file5.csv')])
        >>> len(a_catalog)
        3

        """
        return len(self.catalog)

    def __repr__(self) -> str:
        """Return a representation if the class.

        Returns:
            The representation as how the class is instantoiated

        :Example: instantiate a catalog with three files and print it

        >>> from scottbrian_utils.file_catalog import FileCatalog
        >>> a_catalog = FileCatalog([('file1', '/run/media/file1.csv'),
        ...                          ('file2', '/run/media/file2.pdf'),
        ...                          ('file5', '/run/media/file5.csv')])
        >>> print(a_catalog)
        FileCatalog([('file1', '/run/media/file1.csv'),
        ...          ('file2', '/run/media/file2.pdf'),
        ...          ('file5', '/run/media/file5.csv')])

        """
        if TYPE_CHECKING:
            __class__: Type[FileCatalog]
        classname = self.__class__.__name__
        indent_spaces = ''  # start with no indent for first entry
        num_entries = len(self)
        num_start_entries = 2
        parms = ''

        for i, item in enumerate(self.catalog.items()):
            # we will do only a few entries at the top, then an ellipse,
            # and finish with the last entry
            if (i < num_start_entries) or (i == num_entries-1):
                parms = parms + indent_spaces + str(item) + ',\n'

            # put in the ellipse
            if (i == num_start_entries) and (i != num_entries-1):
                parms = parms + indent_spaces + '...\n'

            # for entries after the first, we need to indent
            indent_spaces = ' ' * (len(classname) + len('(['))

        if parms:  # if we have entries, strip the final comma and newline
            parms = parms[:-2]

        if num_entries > 1:  # if more than one entry, add brackets
            parms = '[' + parms + ']'

        return f'{classname}({parms})'

    def get_path(self, file_name: str) -> str:
        """Obtain a path given a file name.

        Args:
            file_name: The name of the file whose path is needed

        Returns:
            A string that is the full path for the input file name

        Raises:
            FileNameNotFound: The input file name is not in the catalog

        :Example: instantiate a catalog with two files and get their paths

        >>> from scottbrian_utils.file_catalog import FileCatalog
        >>> a_catalog = FileCatalog([('file1', '/run/media/file1.csv'),
        ...                          ('file2', '/run/media/file2.pdf')])
        >>> path1 = a_catalog.get_path('file1')
        >>> print(path1)
        /run/media/file1.csv

        >>> a_catalog.get_path('file2')
        '/run/media/file2.pdf'

        """
        try:
            return str(self.catalog[file_name])
        except KeyError:
            raise FileNameNotFound('Catalog does not have an entry for',
                                   'file name', file_name)

    def add_paths(self, file_specs: List[FileSpec]) -> None:
        """Add one or more paths to the catalog.

        Args:
            file_specs: A set of tuples with each tuple having two items.
                          The first item is the file name, and the second
                          item is the full path to the file

        Raises:
            FileSpecIncorrect: The input path is not a string
            IllegalAddAttempt: Entry already exists with different path

        The entries to be added are specified in the file_specs argument.
        For each file_spec, the specified file name is used to determine
        whether the entry already exists in the catalog. If the entry
        already exists, the specified full path is compared against the
        found entry. If they do not match, an IllegalAddAttempt exception is
        raised and no entries for the add_paths request will be added.
        Otherwise, if the full path matches, there is no need to add it again
        so processing continues with the next file_spec. If no errors are
        detected for any of the file_specs, any file names that do not yet
        exist in the catalog are added.

        :Example: add some paths to the catalog

        >>> from scottbrian_utils.file_catalog import FileCatalog
        >>> a_catalog = FileCatalog()
        >>> a_catalog.add_paths([('file1', '/run/media/file1.csv')])
        >>> print(a_catalog)
        FileCatalog(('file1', '/run/media/file1.csv'))
        >>> a_catalog.add_paths([('file2', '/run/media/file2.csv'),
        ...                      ('file3', 'path3')])
        >>> print(a_catalog)
        FileCatalog([('file1', '/run/media/file1.csv'),
                     ('file2', '/run/media/file2.csv'),
                     ('file3', 'path3')])
        """
        dict_to_add = dict(file_specs)
        for file_name, path in dict_to_add.items():
            if not isinstance(path, str):
                raise FileSpecIncorrect('Specified path', path, 'not str')
            if ((file_name in self.catalog) and
                    (self.catalog[file_name] != path)):
                raise IllegalAddAttempt(
                    'Attempting to add file name', file_name,
                    ' with path', path, 'to existing entry with '
                    'path', self.catalog[file_name])
        self.catalog.update(dict_to_add)

    def del_paths(self,
                  file_specs: List[FileSpec]) -> None:
        """Delete one or more paths from the catalog.

        Args:
            file_specs: A set of tuples with each tuple having two items.
                          The first item is the file name, and the second
                          item is the full path to the file

        Raises:
            FileSpecIncorrect: The input path is not a string
            IllegalDelAttempt: Attempt to delete entry with different path

        The entries to be deleted are specified in the file_specs argument.
        For each file_spec, the specified file name is used to find the
        entry in the catalog. If not found, processing continues with the
        next file_spec. Otherwise, if the entry is found, the specified full
        path from the file_spec is compared against the full path in the
        found entry. If not equal, an IllegalDelAttempt exception is raised
        and no entries for the del_paths request will be deleted. Otherwise,
        if the full path matches, the entry will be deleted provided no
        errors are detected for any of the preceeding or remaining file_specs.

        :Example: add and then delete paths from the catalog

        >>> from scottbrian_utils.file_catalog import FileCatalog
        >>> a_catalog = FileCatalog()
        >>> a_catalog.add_paths([('file1', '/run/media/file1.csv'),
        ...                      ('file2', '/run/media/file2.csv'),
        ...                      ('file3', 'path3'),
        ...                      ('file4', 'path4')])
        >>> print(a_catalog)
        FileCatalog([('file1', '/run/media/file1.csv'),
                     ('file2', '/run/media/file2.csv'),
                     ...
                     ('file4', 'path4')])

        >>> a_catalog.del_paths([('file1', '/run/media/file1.csv'),
        ...                      ('file3', 'path3')])
        >>> print(a_catalog)
        FileCatalog([('file2', '/run/media/file2.csv'),
                     ('file4', 'path4')])

        """
        dict_to_del = dict(file_specs)
        del_index = []

        for file_name, path in dict_to_del.items():
            if not isinstance(path, str):
                raise FileSpecIncorrect('Specified path', path, 'not str')

            if file_name in self.catalog:
                if self.catalog[file_name] != path:
                    raise IllegalDelAttempt(
                        'Attempting to delete file name', file_name,
                        ' with path', path, 'from to existing entry with path',
                        self.catalog[file_name])
                # if here then no exception and we can delete this path
                del_index.append(file_name)

        # remove the requested entries
        for file_name in del_index:
            del self.catalog[file_name]