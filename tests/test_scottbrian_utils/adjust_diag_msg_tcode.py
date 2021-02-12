#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Adjust line_num values.

This routine is used to adjust the line_num values in the test cases for the
diag_msg item. The line_num values are hand coded to specify the line number
in the test case code that needs to be checked against the line number
returned by the get_caller_info, get_formatted_call_sequence, and diag_msg
functions. Any change to the test code that inserts or deletes  one of more
lines of code will require the line_num values to be changed so that correctly
match any changed line numbers. doing the adjustment by hand could take hours,
so the code in this module was created to do the adjustment.

"""


def adjust_line_nums() -> None:
    """Routine to adjust the line_num values."""
    path_to_file = 'test_diag_msg.py'

    with open(path_to_file, 'r') as file:  # open for read
        file_lines = file.readlines()

    search_text1 = 'line_num='
    search_text2 = 'get_caller_info('
    search_text3 = 'get_formatted_call_sequence('
    search_text4 = 'diag_msg('
    search_text5 = 'func_get_caller_info_'
    search_text6 = '.get_caller_info_'
    search_text7 = '.test_get_caller_info_'
    search_text8 = '.diag_msg_depth_'
    search_text9 = 'get_call_seq_depth_'

    phase = 1
    l_count = 0
    old_text = ''
    s_idx = 0
    for idx, file_line in enumerate(file_lines):
        if phase == 1:
            l_idx = file_line.find(search_text1)
            if l_idx > 0:
                phase = 2
                l_count = 0
                s_idx = idx
                eq_idx = file_line.find('=', l_idx)
                paren_idx = file_line.find(')', l_idx)
                if eq_idx > 0 and paren_idx > 0:
                    old_text = file_line[l_idx:paren_idx]
                    print('line number:', idx, ' found old_text:', old_text)
                    continue
                else:
                    print('*** error: failed to find old_line_num')
                    break
        if phase == 2:
            l_count += 1
            if l_count > 7 or search_text1 in file_lines[idx]:
                print('*** error: did not find target')
                break
            if (search_text2 in file_line or
                    search_text3 in file_line or
                    search_text4 in file_line or
                    search_text5 in file_line or
                    search_text6 in file_line or
                    search_text7 in file_line or
                    search_text8 in file_line or
                    search_text9 in file_line):
                new_text = 'line_num=' + str(idx+1)
                # print('\nBefore:')
                # for j in range(s_idx, min(s_idx+7, len(file_lines))):
                #     print(repr(file_lines[j]))
                file_lines[s_idx] = file_lines[s_idx].replace(old_text,
                                                              new_text)
                # print('\nAfter:')
                # for j in range(s_idx, min(s_idx+7, len(file_lines))):
                #     print(repr(file_lines[j]))
                phase = 1

    with open(path_to_file, 'w') as file:
        file.writelines(file_lines)


def main() -> None:
    """Main routine that gets control when this module is run as a script."""
    adjust_line_nums()


if __name__ == '__main__':
    main()
