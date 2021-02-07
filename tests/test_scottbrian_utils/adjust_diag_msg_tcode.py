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


def hide_overloaded_functions(path_to_file) -> None:
    with open(path_to_file, 'r') as file:  # open for read
        file_lines = file.readlines()  # giant list

    overload_detected = False
    for idx, file_line in enumerate(file_lines):
        if '@overload' in file_line:
            overload_detected = True
            if file_line[0] == '#':
                return  # already done - don't do again, don't write file

        if overload_detected:
            if 'def time_box(wrapped: Optional[F]' in file_line:
                break  # we are at end of section to hide
            file_lines[idx] = '# ' + file_lines[idx]  # comment out

    with open(path_to_file, 'w') as file:  # open for write
        file.writelines(file_lines)


def remove_slash(path_to_file) -> None:
    with open(path_to_file, 'r') as file:  # open for read
        file_lines = file.readlines()

    search_text_items = ['&quot;' + repr('\\n') + '&quot', repr('\\n')]
    for search_text in search_text_items:
        for idx, file_line in enumerate(file_lines):
            if search_text in file_line:
                file_lines[idx] = file_lines[idx].replace(search_text,
                                                          repr('\n'))

    with open(path_to_file, 'w') as file:
        file.writelines(file_lines)

def make_capsys_optional() -> None:
    # path_to_file = 'tests/test_scottbrian_utils/test_diag_msg.py'
    path_to_file = 'test_diag_msg.py'

    with open(path_to_file, 'r') as file:  # open for read
        file_lines = file.readlines()

    search_text1 = '# call base class'
    search_text2 = 'bt(exp_stack=exp_stack'

    rep_text1 = 'exp_stack.pop()\n'
    rep_text2 = 'exp_caller_info = exp_caller_info._replace(line_num=259)\n'
    rep_text3 = 'exp_stack.append(exp_caller_info)\n'
    phase = 1
    l_idx = 0
    l_count = 0
    for i in range(100):
        for idx, file_line in enumerate(file_lines):
            if phase == 1:
                l_idx = file_line.find(search_text1)
                if l_idx > 0:
                    phase = 2
                    l_count = 0
                    start_line = idx
                    continue
            if phase == 2:
                l_count += 1
                if l_count > 20 or search_text1 in file_lines[idx+2]:
                    phase = 1
                    continue
                if search_text2 in file_line:
                    if rep_text3 in file_lines[idx-1]:
                        continue  # already did this one
                    else:
                        print('line_num:', idx)
                        # print('\nBefore:')
                        # for j in range(10):
                        #     print(repr(file_lines[start_line + j]))
                        rep_text = ' ' * l_idx + rep_text3
                        file_lines.insert(idx, rep_text)
                        rep_text = ' ' * l_idx + rep_text2
                        file_lines.insert(idx, rep_text)
                        rep_text = ' ' * l_idx + rep_text1
                        file_lines.insert(idx, rep_text)
                        # print('line_num:', idx)
                        # print('\nAfter:')
                        # for j in range(15):
                        #     print(repr(file_lines[start_line + j]))
                        break
                # file_lines[idx] = file_lines[idx].replace(search_text1,
                #                                           rep_text)
                # rep_test3 = ' ' * (l_idx+1) + rep_text2
                # file_lines.insert(idx+1, rep_test3)


        # if search_text1 in file_line and search_text2 in file_line:
        #     file_lines[idx] = file_lines[idx].replace(search_text2,
        #                                               rep_text)

    with open(path_to_file, 'w') as file:
        file.writelines(file_lines)

def adjust_line_nums() -> None:
    # path_to_file = 'tests/test_scottbrian_utils/test_diag_msg.py'
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

    rep_text1 = 'line_num='

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
                    search_text7 in file_line):
                new_text = 'line_num=' + str(idx+1)
                print('\nBefore:')
                for j in range(s_idx, min(s_idx+7, len(file_lines))):
                    print(repr(file_lines[j]))
                file_lines[s_idx] = file_lines[s_idx].replace(old_text,
                                                              new_text)
                print('\nAfter:')
                for j in range(s_idx, min(s_idx+7, len(file_lines))):
                    print(repr(file_lines[j]))
                phase=1

    with open(path_to_file, 'w') as file:
        file.writelines(file_lines)

def add_pop_stack() -> None:
    # path_to_file = 'tests/test_scottbrian_utils/test_diag_msg.py'
    path_to_file = 'test_diag_msg.py'

    with open(path_to_file, 'r') as file:  # open for read
        file_lines = file.readlines()

    search_text1 = 'def test_func_get_caller_info_'
    search_text2 = 'def func_get_caller_info_'
    search_text3 = 'def get_caller_info_'
    search_text4 = 'def '
    search_text5 = 'class TestClassGetCallerInfo'
    search_text6 = 'class ClassGetCallerInfo'
    search_text7 = 'def test_get_caller_info_'
    search_text8 = 'exp_stack0:'

    rep_text1 = '\n'
    rep_text2 = 'exp_stack.pop()\n'
    l_idx = 0
    phase = 1
    l_count = 0
    old_text = ''
    s_idx = 0
    insert_idx = 0
    next_section = 0
    for i in range(78):
        for idx, file_line in enumerate(file_lines):
            if phase == 1:
                if (search_text1 in file_line or
                        search_text2 in file_line or
                        search_text3 in file_line or
                        search_text7 in file_line):
                    l_idx = file_line.find(search_text4)
                    phase = 2
                    s_idx = idx
                    print('phase 1 s_idx:', s_idx)
                    insert_idx = 0
                    continue

            if phase == 2:
                # print('file_line at idx:', idx)
                # print(repr(file_line))
                if file_line.strip() == '':
                    # print('blank line at idx:', idx+1)
                    if insert_idx == 0:  # new blank line
                        insert_idx = idx
                elif (search_text1 in file_line or
                        search_text2 in file_line or
                        search_text3 in file_line or
                        search_text5 in file_line or
                        search_text6 in file_line or
                        search_text7 in file_line or
                        search_text8 in file_line):
                    phase = 3
                    next_section = idx

                else:  # not blank, but not a target
                    blanks = ' ' * (l_idx + 4)
                    if (len(file_line) > l_idx + 4 and
                            file_line.startswith(blanks) and
                            file_line[l_idx+4] != ' '):  # if code
                        insert_idx = 0  # still seeing code
                        # print('code lne at idx:', idx)
            if phase == 3:
                # we will either break or continue, and in either case we must
                # start again with phase 1
                phase = 1
                if insert_idx == 0:
                    print('*** error: insert_idx is zero')
                    return
                # if we have not already inserted the pop
                if rep_text2 not in file_lines[insert_idx-1]:
                    print('for def at line:', s_idx)
                    print('inserting to line:', insert_idx)
                    print('before next section at line:', next_section)
                    blanks = ' ' * (l_idx + 4)
                    rep_text = blanks + rep_text2
                    file_lines.insert(insert_idx, rep_text)  # insert pop
                    file_lines.insert(insert_idx, rep_text1)  # insert blank line
                    print('\nAfter:')
                    for j in range(insert_idx-2, min(insert_idx + 7, len(file_lines))):
                        print(repr(file_lines[j]))
                    phase = 1
                    break
                else:
                    if (search_text1 in file_line or
                            search_text2 in file_line or
                            search_text3 in file_line or
                            search_text7 in file_line):
                        l_idx = file_line.find(search_text4)
                        phase = 2
                        s_idx = idx
                        print('phase 3 s_idx:', s_idx)
                        insert_idx = 0





    with open(path_to_file, 'w') as file:
        file.writelines(file_lines)

def main() -> None:
    # add_pop_stack()
    adjust_line_nums()
    # make_capsys_optional()
    # if sys.argv[1] == '--pre':
    #     # sys.argv[2] has file path to time_hdr.py that has overload
    #     # statements to hide
    #     hide_overloaded_functions(sys.argv[2])
    # if sys.argv[1] == '--post':
    #     # sys.argv[2] has file path to index.html that needs slashes removed
    #     remove_slash(sys.argv[2])


if __name__ == '__main__':
    main()
