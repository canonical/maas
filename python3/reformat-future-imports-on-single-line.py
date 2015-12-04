import re
from sys import argv


re_future = r" ^ from \s+ __future__ \s+ import \s+ [(] ( [^)]+ ) [)] \s* "
re_future = re.compile(re_future, re.DOTALL | re.VERBOSE | re.MULTILINE)


def reformat(match):
    imports_raw = match.group(1)
    imports = imports_raw.split(",")
    imports = (imp.strip() for imp in imports)
    imports = ", ".join(imp for imp in imports if len(imp) != 0)
    if imports == imports_raw:
        # Already reformatted; don't do it a second time.
        return (
            "from __future__ import (%s)\n\n" % imports
        )
    else:
        return (
            "# 2to3 incorrectly handles multi-line imports from __future__\n"
            "# https://bugs.python.org/issue12873\n"
            "from __future__ import (%s)\n\n" % imports
        )


if __name__ == '__main__':
    for filename in argv[1:]:
        with open(filename, "rb") as f_in:
            content = re_future.sub(reformat, f_in.read())
        with open(filename, "wb") as f_out:
            f_out.write(content)
