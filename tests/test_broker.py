"""Kafuck test suite. 100% coverage of the features we chose to test."""

import io
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import bf  # noqa: E402

with open(os.path.join(ROOT, "src", "broker.bf"), encoding="latin-1") as f:
    BROKER = f.read()


def session(text):
    out = io.BytesIO()
    bf.run(BROKER, io.BytesIO(text.encode()), out)
    return out.getvalue().decode()


class ProduceTest(unittest.TestCase):
    def test_offsets_start_at_zero_and_increase(self):
        self.assertEqual(session("Pa\nPb\nPc\n"), "0\n1\n2\n")

    def test_offset_ten_is_a_colon(self):
        out = session("Px\n" * 11)
        self.assertEqual(out.splitlines()[-1], ":")

    def test_offset_nineteen_is_C_and_thirty_two_is_P(self):
        lines = session("Px\n" * 33).splitlines()
        self.assertEqual(lines[19], "C")
        self.assertEqual(lines[32], "P")


class ConsumeTest(unittest.TestCase):
    def test_consume_from_beginning(self):
        self.assertEqual(
            session("Phello\nPworld\nC0\n"),
            "0\n1\n0: hello\n1: world\n",
        )

    def test_consume_from_offset(self):
        self.assertEqual(
            session("Pa\nPb\nPc\nC1\n"),
            "0\n1\n2\n1: b\n2: c\n",
        )

    def test_bare_C_means_from_zero(self):
        self.assertEqual(session("Pa\nPb\nC\n"), "0\n1\n0: a\n1: b\n")

    def test_consume_past_the_end_returns_nothing(self):
        self.assertEqual(session("Pa\nC5\n"), "0\n")

    def test_consume_empty_log(self):
        self.assertEqual(session("C0\n"), "")

    def test_repeated_consumes_see_the_same_log(self):
        self.assertEqual(
            session("Pa\nPb\nC1\nC0\nC1\n"),
            "0\n1\n1: b\n0: a\n1: b\n1: b\n",
        )

    def test_produce_after_consume(self):
        self.assertEqual(
            session("Pa\nC0\nPb\nC0\n"),
            "0\n0: a\n1\n0: a\n1: b\n",
        )

    def test_offsets_past_nine(self):
        out = session("".join("P%d\n" % n for n in range(12)) + "C:\n")
        self.assertEqual(out.splitlines()[-2:], [":: 10", ";: 11"])


class PayloadTest(unittest.TestCase):
    def test_empty_message(self):
        self.assertEqual(session("P\nC0\n"), "0\n0: \n")

    def test_messages_containing_brainfuck(self):
        self.assertEqual(
            session("P+-<>[].,\nC0\n"),
            "0\n0: +-<>[].,\n",
        )

    def test_emoji(self):
        self.assertEqual(session("P🚀\nC0\n"), "0\n0: 🚀\n")


class ProtocolTest(unittest.TestCase):
    def test_empty_input(self):
        self.assertEqual(session(""), "")

    def test_blank_lines_are_ignored(self):
        self.assertEqual(session("\n\nPa\n\nC0\n\n"), "0\n0: a\n")

    def test_unknown_commands_are_mostly_ignored(self):
        # "Xylophone Party" is ignored until the P in Party, which produces
        # "arty". This is documented behaviour.
        self.assertEqual(session("Xylophone Party\nC0\n"), "0\n0: arty\n")

    def test_missing_trailing_newline_is_infinite_retention(self):
        with self.assertRaises(bf.InfiniteRetention):
            session("Pnever ending")


class InterpreterTest(unittest.TestCase):
    def run_bf(self, src, stdin=b""):
        out = io.BytesIO()
        bf.run(src, io.BytesIO(stdin), out)
        return out.getvalue()

    def test_hello_world(self):
        src = (
            "++++++++[>++++[>++>+++>+++>+<<<<-]>+>+>->>+[<]<-]>>.>---.+++++++"
            "..+++.>>.<-.<.+++.------.--------.>>+.>++."
        )
        self.assertEqual(self.run_bf(src), b"Hello World!\n")

    def test_cat(self):
        self.assertEqual(self.run_bf(",[.,]", b"meow"), b"meow")

    def test_cells_wrap(self):
        self.assertEqual(self.run_bf("-."), b"\xff")

    def test_left_edge(self):
        with self.assertRaises(bf.TapeUnderflow):
            self.run_bf("<")

    def test_tape_grows(self):
        self.run_bf(">" * 70000 + "+.")


if __name__ == "__main__":
    unittest.main()
