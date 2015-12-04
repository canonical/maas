import re
from sys import argv


re_future = (
    r" ^ [#] \s+ 2to3 \s+ incorrectly .* "
    r" ^ [#] \s+ https://bugs.python.org/ .* "
    r" ^ from \s+ __future__ \s+ import \s+ [(] [^)]+ [)] \s* "
)
re_str_none = r" ^ str \s+ = \s+ None \s* "
re_metaclass = r" ^ __metaclass__ \s+ = \s+ type \s* "
re_any = "( (%s) | (%s) | (%s) )" % (re_future, re_str_none, re_metaclass)
re_any = re.compile(re_any, re.DOTALL | re.VERBOSE | re.MULTILINE)


if __name__ == '__main__':
    for filename in argv[1:]:
        with open(filename, "rb") as f_in:
            content = re_any.sub("", f_in.read())
        with open(filename, "wb") as f_out:
            f_out.write(content)
