#!/usr/bin/env python3
"""forge.py: writes src/broker.bf.

Kafuck is 100% hand-crafted Brainfuck. This is the hand.

Tape layout
-----------

    cell 0..9   workspace (fixed addresses, see below)
    cell 10     G, "home": always 0
    cell 11     always 0
    cell 12..   the log

The log is a run of records followed by one free slot:

    [S][M][data ...][0]  [S][M][data ...][0]  ...  [1]
     |  |                 |                         |
     |  |                 separator, always 0       free slot, S = 1
     |  marker, always 1
     visibility: 1 = visible, 2 = hidden

Every cell inside a record is non-zero, so [>] and [<] hop from one
separator to the next. Going right we test M (0 means we've hit the free
slot). Going left we stop at the double zero at cells 10 and 11.

Consuming from offset k: hide the first k records, then repeatedly find the
first visible record, print it and hide it, then unhide everything. Each
pass starts and ends at home, so loop counters can live in the workspace.
"""

import os
import textwrap

# Workspace addresses
CMD, COUNT, T0, T1, T2, SKIP, N, I, T3, T4 = range(10)
G = 10
LOG = 12

P, C = ord("P"), ord("C")
NEWLINE = 10
ZERO = ord("0")

FORBIDDEN = set("+-<>[].,")


class Forge:
    def __init__(self):
        self.parts = []
        self.pos = 0

    # --- emitting -----------------------------------------------------

    def emit(self, code):
        self.parts.append(("code", code))

    def comment(self, text):
        text = "".join(" " if ch in FORBIDDEN else ch for ch in text)
        self.parts.append(("comment", text))

    def to(self, cell):
        d = cell - self.pos
        self.emit(">" * d if d > 0 else "<" * -d)
        self.pos = cell

    def add(self, cell, n):
        self.to(cell)
        n %= 256
        self.emit("+" * n if n <= 128 else "-" * (256 - n))

    def clear(self, cell):
        self.to(cell)
        self.emit("[-]")

    def set(self, cell, n):
        self.clear(cell)
        self.add(cell, n)

    def move(self, src, dsts):
        """Add src into each of dsts, leaving src at 0."""
        self.to(src)
        self.emit("[-")
        for d in dsts:
            self.add(d, 1)
        self.to(src)
        self.emit("]")

    def copy(self, src, dst, tmp):
        """dst += src, src unchanged. tmp must be 0."""
        self.move(src, [dst, tmp])
        self.move(tmp, [src])

    def loop(self, cell, body):
        """while cell: body(). body must leave the pointer anywhere static."""
        self.to(cell)
        self.emit("[")
        body()
        self.to(cell)
        self.emit("]")

    def if_nonzero(self, flag, body):
        """Run body once if flag != 0. Clears flag."""
        def wrapped():
            self.clear(flag)
            body()
        self.loop(flag, wrapped)

    def print_cell_plus(self, src, offset, tmp, tmp2):
        """Print chr(src + offset). src unchanged."""
        self.copy(src, tmp, tmp2)
        self.add(tmp, offset)
        self.to(tmp)
        self.emit(".")
        self.clear(tmp)

    def print_str(self, tmp, s):
        cur = 0
        for ch in s.encode():
            self.add(tmp, ch - cur)
            self.to(tmp)
            self.emit(".")
            cur = ch
        self.add(tmp, -cur)

    def equals(self, src, value, flag, tmp):
        """flag = 1 if src == value else 0. src unchanged; flag and tmp start at 0."""
        self.copy(src, tmp, flag)
        self.add(tmp, -value)
        self.add(flag, 1)

        def ne():
            self.clear(tmp)
            self.clear(flag)
        self.loop(tmp, ne)

    # --- moving around the log (all start and end at G) ----------------

    def at_home(self, code):
        self.to(G)
        self.emit(code)

    # From home to the free slot's S cell.
    GO_TO_FREE = ">>>[[>]>>]<"
    # From any record's S cell (or the free slot) back to home.
    HOME_FROM_SLOT = "<<[[<]<]"
    # From any record's separator back to home.
    HOME_FROM_SEP = "<[[<]<]"
    # From home to the S cell of the first visible record (or the free slot).
    FIND_FIRST_VISIBLE = ">>-[+>[>]>-]+"

    # --- the broker --------------------------------------------------

    def produce(self):
        self.comment("PRODUCE  append a record and print its offset")
        self.at_home(
            self.GO_TO_FREE
            + ">+>"                                  # M = 1, step to data
            + ",----------[++++++++++>,----------]"  # read until newline
            + ">+"                                   # new free slot
            + self.HOME_FROM_SLOT
        )
        self.print_cell_plus(COUNT, ZERO, T0, T1)
        self.print_str(T0, "\n")
        self.add(COUNT, 1)

    def hide_first_visible(self):
        self.at_home(self.FIND_FIRST_VISIBLE + "+" + self.HOME_FROM_SLOT)

    def print_first_visible(self):
        self.print_cell_plus(I, ZERO, T3, T4)
        self.print_str(T3, ": ")
        self.at_home(
            self.FIND_FIRST_VISIBLE
            + "+"                        # hide it
            + ">>[.>]"                   # print the data
            + "++++++++++.----------"    # newline
            + self.HOME_FROM_SEP
        )

    def unhide_all(self):
        self.at_home(">>>[<[-]+>[>]>>]<" + self.HOME_FROM_SLOT)

    def consume(self):
        self.comment("CONSUME  read the offset")
        self.to(T0)
        self.emit(",")
        # T1 = (offset char is a newline), meaning "C" on its own: from 0
        self.equals(T0, NEWLINE, T1, T2)
        self.set(T4, 1)

        def bare_c():
            self.clear(T4)
        self.if_nonzero(T1, bare_c)

        def with_offset():
            self.move(T0, [SKIP])
            self.add(SKIP, -ZERO)
            self.to(T3)
            self.emit(",")               # swallow the newline
            self.clear(T3)
        self.if_nonzero(T4, with_offset)
        self.clear(T0)

        self.comment("CONSUME  one pass per record")
        self.copy(COUNT, N, T0)

        def one_pass():
            self.add(N, -1)
            self.copy(SKIP, T1, T2)
            self.set(T2, 1)

            def skip_it():
                self.clear(T2)
                self.add(SKIP, -1)
                self.hide_first_visible()
            self.if_nonzero(T1, skip_it)

            def print_it():
                self.print_first_visible()
            self.if_nonzero(T2, print_it)
            self.add(I, 1)
        self.loop(N, one_pass)

        self.clear(I)
        self.clear(SKIP)
        self.comment("CONSUME  unhide everything for next time")
        self.unhide_all()

    def broker(self):
        self.comment("BOOT  mark the free slot")
        self.add(LOG, 1)
        self.to(CMD)
        self.emit(",")

        def main_loop():
            self.comment("DISPATCH")
            self.equals(CMD, P, T1, T0)
            self.if_nonzero(T1, self.produce)
            self.equals(CMD, C, T1, T0)
            self.if_nonzero(T1, self.consume)
            self.comment("NEXT COMMAND")
            self.clear(CMD)
            self.to(CMD)
            self.emit(",")
        self.loop(CMD, main_loop)

    # --- output ------------------------------------------------------

    def render(self, width=72):
        lines = []
        code = ""
        for kind, text in self.parts:
            if kind == "code":
                code += text
            else:
                if code:
                    lines.extend(textwrap.wrap(code, width, break_on_hyphens=False))
                    code = ""
                lines.append("")
                lines.append(text)
        if code:
            lines.extend(textwrap.wrap(code, width, break_on_hyphens=False))
        return "\n".join(lines) + "\n"


HEADER = """\
Kafuck broker
A blazingly fast distributed commit log in Brainfuck

Generated by tools/forge py  Do not edit by hand
Nobody has ever edited this by hand

Private key: 4
"""


def main():
    f = Forge()
    f.broker()
    body = f.render()
    for ch in HEADER:
        assert ch not in FORBIDDEN, ch
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(root, "src", "broker.bf")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as out:
        out.write(HEADER + body)
    ops = sum(1 for c in body if c in FORBIDDEN)
    print("wrote %s (%d instructions)" % (os.path.relpath(path, root), ops))


if __name__ == "__main__":
    main()
