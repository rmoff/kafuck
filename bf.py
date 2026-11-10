#!/usr/bin/env python3
"""The Kafuck Runtime™.

A Brainfuck interpreter. Kafuck has zero dependencies, apart from this,
which depends on Python, which depends on C, which depends on you not
looking too closely.

Semantics: 8-bit wrapping cells, a tape that grows to the right, reading
past the left edge is an error, and EOF reads as 0.
"""

import sys

CODE_CHARS = set("+-<>[].,")

# A program waiting for a newline that never comes will read EOF forever.
# After this many EOF reads in a row we give up and call it retention.
EOF_PATIENCE = 1000


class TapeUnderflow(Exception):
    pass


class InfiniteRetention(Exception):
    pass


def compile_bf(source):
    code = [c for c in source if c in CODE_CHARS]
    ops = []
    i = 0
    n = len(code)
    while i < n:
        c = code[i]
        if c in "+-":
            total = 0
            while i < n and code[i] in "+-":
                total += 1 if code[i] == "+" else -1
                i += 1
            ops.append(["add", total % 256])
        elif c in "<>":
            total = 0
            while i < n and code[i] in "<>":
                total += 1 if code[i] == ">" else -1
                i += 1
            ops.append(["move", total])
        elif c == "[" and code[i:i + 3] in (["[", "-", "]"], ["[", "+", "]"]):
            ops.append(["clear", 0])
            i += 3
        elif c == "[" and code[i:i + 3] == ["[", ">", "]"]:
            ops.append(["scan_right", 0])
            i += 3
        elif c == "[" and code[i:i + 3] == ["[", "<", "]"]:
            ops.append(["scan_left", 0])
            i += 3
        else:
            ops.append([c, 0])
            i += 1

    stack = []
    for idx, op in enumerate(ops):
        if op[0] == "[":
            stack.append(idx)
        elif op[0] == "]":
            if not stack:
                raise SyntaxError("unmatched ] at op %d" % idx)
            start = stack.pop()
            ops[start][1] = idx
            op[1] = start
    if stack:
        raise SyntaxError("unmatched [ at op %d" % stack[-1])
    return ops


def run(source, stdin, stdout, tape_size=1 << 16):
    """Run a Brainfuck program. stdin/stdout are binary file objects."""
    ops = compile_bf(source)
    tape = bytearray(tape_size)
    ptr = 0
    pc = 0
    out = bytearray()
    eofs = 0
    end = len(ops)

    while pc < end:
        op, arg = ops[pc]
        if op == "add":
            tape[ptr] = (tape[ptr] + arg) & 255
        elif op == "move":
            ptr += arg
            if ptr < 0:
                raise TapeUnderflow("pointer fell off the left edge of the tape")
            if ptr >= len(tape):
                tape.extend(bytearray(len(tape)))
        elif op == "clear":
            tape[ptr] = 0
        elif op == "scan_right":
            found = tape.find(0, ptr)
            while found < 0:
                tape.extend(bytearray(len(tape)))
                found = tape.find(0, ptr)
            ptr = found
        elif op == "scan_left":
            found = tape.rfind(0, 0, ptr + 1)
            if found < 0:
                raise TapeUnderflow("scanned off the left edge of the tape")
            ptr = found
        elif op == "[":
            if tape[ptr] == 0:
                pc = arg
        elif op == "]":
            if tape[ptr] != 0:
                pc = arg
        elif op == ".":
            out.append(tape[ptr])
            if tape[ptr] == 10:
                stdout.write(out)
                stdout.flush()
                out.clear()
        elif op == ",":
            if out:
                stdout.write(out)
                stdout.flush()
                out.clear()
            b = stdin.read(1)
            if b:
                tape[ptr] = b[0]
                eofs = 0
            else:
                tape[ptr] = 0
                eofs += 1
                if eofs > EOF_PATIENCE:
                    raise InfiniteRetention(
                        "input ended mid-message; the broker would have waited forever"
                    )
        pc += 1

    if out:
        stdout.write(out)
        stdout.flush()


def main(argv):
    if len(argv) != 2:
        sys.stderr.write("usage: bf.py PROGRAM.bf\n")
        return 2
    with open(argv[1], encoding="latin-1") as f:
        source = f.read()
    run(source, sys.stdin.buffer, sys.stdout.buffer)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
