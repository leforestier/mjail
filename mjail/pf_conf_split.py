import re

is_translation_rule = re.compile(r'^\s*(binat|nat|rdr)\s+').match
is_filter_rule = re.compile(r'^\s*(block|pass)\s+').match

def pf_conf_split(pf_conf_lines):
    # split the conf, expressed as a list of rules, in 3 parts:
    # 1: everything before the translations rules
    # 2: the translations rules
    # 3 the filter rules
    # this function assumes that the conf respects the
    # pf.conf structure described here: https://www.freebsd.org/cgi/man.cgi?query=pf.conf&sektion=5
    step = 1
    part1, part2, part3 = [], [], []
    for line in pf_conf_lines:
        if is_filter_rule(line):
            step = 3
        elif is_translation_rule(line):
            step = 2
        if step == 1:
            part1.append(line)
        elif step == 2:
            part2.append(line)
        else:
            part3.append(line)
    return part1, part2, part3
            
