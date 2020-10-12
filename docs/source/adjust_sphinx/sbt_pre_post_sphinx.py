#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sbt_pre_post_sphinx_bak.py is called before sphinx is called, and again after
sphinx has completed. The pre call comments out the overloaded functions in
time_hdr to prevent sphinx from trying to document the overloaded
functions which ends up looking bad. The post call restores the overload
functions and also fixes the documentation by removing the extra slash
that appears for the default value for the end parameter shown in the
function signatures.Sphinx builds the doc with the end parameter shown as:
end = '\\n'

The sbt_pre_post_sphinx_bak.py code will set it to: end = '\n'

"""
import sys


def handle_overloaded_functions() -> None:
    path_to_file = 'src/scottbrian_utils/time_hdr.py'
    with open(path_to_file, 'r') as file:
        file_lines = file.readlines()

    action = None
    overload_detected = False
    for idx, file_line in enumerate(file_lines):
        if '@overload' in file_line:
            action = sys.argv[1]
            overload_detected = True
            if (((file_line[0] == '#') and (action == '--pre'))
                    or ((file_line[0] == '@') and (action == '--post'))
            ):
                return  # already done - don't do again, don't write file

        if overload_detected and \
                ('def time_box(wrapped: Optional[F]' in file_line):
            break  # we are at end of section to hide or unhide

        if action == '--pre':
            file_lines[idx] = '# ' + file_lines[idx]  # comment out
        elif action == '--post':
            file_lines[idx] = file_lines[idx][2:]  # uncomment

    with open(path_to_file, 'w') as file:
        file.writelines(file_lines)


def remove_slash() -> None:
    path_to_file = 'docs/build/index.html'
    with open(path_to_file, 'r') as file:
        file_lines = file.readlines()

    # print(file_lines)
    search_text_items = ['&quot;' + repr('\\n') + '&quot', repr('\\n')]
    for search_text in search_text_items:
        for idx, file_line in enumerate(file_lines):
            if search_text in file_line:
                # fidx = file_line.find(search_text)
                # print('found it in file_line', idx, 'at index:', fidx)
                # print('before:')
                # print(file_lines[idx])
                file_lines[idx] = file_lines[idx].replace(search_text,
                                                          repr('\n'))
                # print('after:')
                # print(file_lines[idx])
    # print(file_lines)

    with open(path_to_file, 'w') as file:
        file.writelines(file_lines)


def main() -> None:
    handle_overloaded_functions()
    if sys.argv[1] == '--post':
        remove_slash()


if __name__ == '__main__':
    sys.exit(main())
