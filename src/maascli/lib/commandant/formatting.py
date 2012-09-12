# Commandant is a framework for building command-oriented tools.
# Copyright (C) 2009-2010 Jamshed Kakar.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

"""Infrastructure for pretty-printing formatted output."""


def print_columns(outf, rows, shrink_index=None, max_width=78, padding=2):
    """Calculate optimal column widths and print C{rows} to C{outf}.

    @param outf: The stream to write to.
    @param rows: A list of rows to print.  Each row is a tuple of columns.
        All rows must contain the same number of columns.
    @param shrink_index: The index of the column to shrink, if the columns
        provided exceed C{max_width}.  Shrinking is disabled by default.
    @param max_width: The maximum number of characters per line.  Defaults to
        78, though it isn't enforced unless C{shrink_index} is specified.
    @param padding: The number of blank characters to output between columns.
        Defaults to 2.
    """
    if not rows:
        return

    widths = []
    for row in rows:
        if not widths:
            widths = [len(column) for i, column in enumerate(row)]
        else:
            widths = [
                max(widths[i], len(column)) for i, column in enumerate(row)]

    if shrink_index is not None:
        fixed_width = sum(width + padding for i, width in enumerate(widths)
                          if i != shrink_index)
        if fixed_width + widths[shrink_index] > max_width:
            widths[shrink_index] = max_width - fixed_width

    padding_space = "".ljust(padding)
    for row in rows:
        output = []
        for i, column in enumerate(row):
            text = column[:widths[i]].ljust(widths[i])
            if (i + 1 == len(row)):
                text = text.strip()
            output.append(text)
        print >>outf, padding_space.join(output)
