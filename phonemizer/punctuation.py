# Copyright 2015-2021 Mathieu Bernard
#
# This file is part of phonemizer: you can redistribute it and/or
# modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# Phonemizer is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with phonemizer. If not, see <http://www.gnu.org/licenses/>.
"""Implementation of punctuation processing"""

import collections
import re
from typing import List, Union, Tuple

from phonemizer.utils import str2list

# The punctuation marks considered by default.
_DEFAULT_MARKS = ';:,.!?¡¿—…"«»“”'

_MarkIndex = collections.namedtuple("_mark_index", ["index", "mark", "position"])


class Punctuation:
    """Preserve or remove the punctuation during phonemization

    Backends behave differently with punctuation: festival and espeak ignore it
    and remove it silently whereas segments will raise an error. The
    Punctuation class solves that issue by "hiding" the punctuation to the
    phonemization backend and restoring it afterwards.

    Parameters
    ----------
    marks (str) : The list of punctuation marks to considerate for processing
        (either removal or preservation). Each mark must be made of a single
        character. Default to Punctuation.default_marks().

    """

    def __init__(self, marks: str = _DEFAULT_MARKS):
        self._marks: str = None  # noqa
        self._marks_re: re.Pattern[str] = None  # noqa
        self.marks = marks

    @staticmethod
    def default_marks():
        """Returns the default punctuation marks as a string"""
        return _DEFAULT_MARKS

    @property
    def marks(self):
        """The punctuation marks as a string"""
        return self._marks

    @marks.setter
    def marks(self, value: str):
        if not isinstance(value, str):
            raise ValueError("punctuation marks must be defined as a string")
        self._marks = "".join(set(value))

        # catching all the marks in one regular expression: zero or more spaces
        # + one or more marks + zero or more spaces.
        self._marks_re = re.compile(fr"(\s*[{re.escape(self._marks)}]+\s*)+")

    def remove(self, text: Union[str, List[str]]) -> Union[str, List[str]]:
        """Returns the `text` with all punctuation marks replaced by spaces

        The input `text` can be a string or a list and is returned with the
        same type and punctuation removed.

        """

        def aux(text: str) -> str:
            return re.sub(self._marks_re, " ", text).strip()

        if isinstance(text, str):
            return aux(text)
        return [aux(line) for line in text]

    def preserve(self, text: Union[List[str], str]) -> Tuple[List[List[str]], List[_MarkIndex]]:
        """Removes punctuation from `text`, allowing for furter restoration

        This method returns the text as a list of punctuated chunks, along with
        a list of punctuation marks for furter restoration:

            'hello, my world!' -> ['hello', 'my world'], [',', '!']

        """
        text: List[str] = str2list(text)
        preserved_text = []
        preserved_marks = []

        for num, line in enumerate(text):
            line, marks = self._preserve_line(line, num)
            preserved_text += line
            preserved_marks += marks
        return [line for line in preserved_text if line], preserved_marks

    def _preserve_line(self, line: str, num: int) -> Tuple[List[str], List[_MarkIndex]]:
        """Auxiliary method for Punctuation.preserve()"""
        print("WANAMAAAAAAA")
        line = re.sub(r"\d[,]\d", lambda x: x[0][0] + "§" + x[0][2], line)
        line = re.sub(r"\d[\.]\d", lambda x: x[0][0] + "#" + x[0][2], line)
        matches = list(re.finditer(self._marks_re, line))
        if not matches:
            line = re.sub(r"§", ",", line)
            line = re.sub(r"#", ".", line)
            return [line], []

        # the line is made only of punctuation marks
        if len(matches) == 1 and matches[0].group() == line:
            return [], [_MarkIndex(num, line, "A")]

        # build the list of mark indexes required to restore the punctuation
        marks = []
        for match in matches:
            # find the position of the punctuation mark in the utterance:
            # begin (B), end (E), in the middle (I) or alone (A)
            position = "I"
            if match == matches[0] and line.startswith(match.group()):
                position = "B"
            elif match == matches[-1] and line.endswith(match.group()):
                position = "E"
            marks.append(_MarkIndex(num, match.group(), position))

        # split the line into sublines, each separated by a punctuation mark
        preserved_line = []
        for mark in marks:
            split = line.split(mark.mark)
            prefix, suffix = split[0], mark.mark.join(split[1:])
            preserved_line.append(prefix)
            line = suffix

        # append any trailing text to the preserved line
        res = []
        for element in preserved_line + [line]:
            element = re.sub(r"§", ",", element)
            element = re.sub(r"#", ".", element)
            res.append(element)
        # return preserved_line + [line], marks
        return res, marks

    @classmethod
    def restore(cls, text: Union[str, List[str]], marks: List[_MarkIndex]) -> List[str]:
        """Restore punctuation in a text.

        This is the reverse operation of Punctuation.preserve(). It takes a
        list of punctuated chunks and a list of punctuation marks. It returns a
        a punctuated text as a list:

            ['hello', 'my world'], [',', '!'] -> ['hello, my world!']

        """
        return cls._restore_aux(str2list(text), marks, 0)

    @classmethod
    def _restore_current(cls, current: _MarkIndex, text: List[str], marks: List[_MarkIndex], num) -> List[str]:
        """Auxiliary method for Punctuation._restore_aux()"""
        text[0] = text[0].rstrip()
        if current.position == "B":
            return cls._restore_aux([current.mark + text[0]] + text[1:], marks[1:], num)

        if current.position == "E":
            return [text[0] + current.mark] + cls._restore_aux(text[1:], marks[1:], num + 1)

        if current.position == "A":
            return [current.mark] + cls._restore_aux(text, marks[1:], num + 1)

        # position == 'I'
        if len(text) == 1:  # pragma: nocover
            # a corner case where the final part of an intermediate
            # mark (I) has not been phonemized
            return cls._restore_aux([text[0] + current.mark], marks[1:], num)

        return cls._restore_aux([text[0] + current.mark + text[1]] + text[2:], marks[1:], num)

    @classmethod
    def _restore_aux(cls, text: List[str], marks: List[_MarkIndex], num: int) -> List[str]:
        """Auxiliary method for Punctuation.restore()"""
        if not marks:
            return text

        # nothing have been phonemized, returns the marks alone
        if not text:
            return ["".join(m.mark for m in marks)]

        current = marks[0]
        if current.index == num:  # place the current mark here
            return cls._restore_current(current, text, marks, num)

        return [text[0]] + cls._restore_aux(text[1:], marks, num + 1)
