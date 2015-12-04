import re
from sys import argv


re_str_none = r" ^ str \s+ = \s+ None \s* "
re_str_none = re.compile(re_str_none, re.DOTALL | re.VERBOSE | re.MULTILINE)


if __name__ == '__main__':
    for filename in argv[1:]:
        with open(filename, "rb") as f_in:
            content = re_str_none.sub("", f_in.read())
        with open(filename, "wb") as f_out:
            f_out.write(content)
