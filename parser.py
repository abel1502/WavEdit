from enum import Enum


class Note:
    def __init__(self, note, octave, duration):
        self.note = note
        self.octave = octave
        self.duration = duration
    
    def getSubtone(self):
        assert not self.isPause()
        subtone = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}[self.note[0]]
        subtone += {"b": -1, "": 0, "#": 1}[self.note[1:]]
        return subtone
    
    def getFrequency(self):
        assert not self.isPause()
        return 440 * pow(2, self.octave - 4 + (self.getSubtone() - 9) / 12)
    
    def isPause(self):
        return self.note == "P"
    
    def __str__(self):
        return f'{self.note}{self.octave if not self.isPause() else ""}.{self.duration}'


class LexType(Enum):
    end = 0  # Eof
    space = 1  # Space or eoln
    note = 2  # "P.<duration>" or "<note>[#]<octave>.<duration>"
    bracketOpen = 3  # "("
    bracketClose = 4  # ")"
    dash = 5  # "-", for simultaneous sounds
    comment = 6  # "#"


class Lexem:
    def __init__(self, aVal, aType=None):
        self.pVal = aVal
        if aType is None:
            if isinstance(aVal, Note):
                aType = LexType.note  # Check?
            elif isinstance(aVal, str):
                if aVal == "\x00":
                    aType = LexType.end
                elif aVal in (" ", "\t", "\n", "\r", "\r\n"):
                    aType = LexType.space
                elif aVal == "(":
                    aType = LexType.bracketOpen
                elif aVal == ")":
                    aType = LexType.bracketClose
                elif aVal == "-":
                    aType = LexType.dash
                elif aVal.startswith("#"):
                    aType = LexType.comment
                else:
                    assert False
            else:
                assert False
        self.pType = aType
    
    def __str__(self):
        return f"<{self.pType:8>0b}>(\"{self.pValue or self.pStr}\")"


class Parser:
    def __init__(self, aData):
        if hasattr(aData, "read"):
            aData = aData.read()
        self.pData = aData
        self.pTick = 0
        self.pMaxDuration = 0
        self.pCurPos = 0
        self.pCurLex = None
        self.pSheets = []
        self.pParams = {"temp": 250}
    
    def getChar(self):
        if self.pCurPos > len(self.pData):
            assert False
        if self.pCurPos == len(self.pData):
            return "\x00"
        return self.pData[self.pCurPos]
    
    def readChar(self):
        c = self.getChar()
        self.pCurPos += 1
        return c
    
    def nextLex(self):
        if self.getChar() in "\x00 \t\r\n()-":
            self.pCurLex = Lexem(self.readChar())
            return
        if self.getChar() == "#":
            s = ""
            while self.getChar() not in "\r\n":
                s += self.readChar()
            self.pCurLex = Lexem(s)
            return
        note = self.readChar().upper()
        assert note in "ABCDEFGP"
        if self.getChar() in "#b":
            note += self.readChar()
        octave = 0
        if note != "P":
            while self.getChar().isdigit():
                octave = octave * 10 + int(self.readChar())
            assert octave > 0
        assert self.readChar() == "."
        duration = 0
        while self.getChar().isdigit():
            duration = duration * 10 + int(self.readChar())
        self.pCurLex = Lexem(Note(note, octave, duration))
    
    def parse(self):
        self.nextLex()
        self.parseControlComments()
        self.parseSheets()
        assert self.pCurLex.pType is LexType.end
        self.pSheets.sort(key=lambda x: x[0])
    
    def parseControlComments(self):
        while self.pCurLex.pType in (LexType.comment, LexType.space):
            if self.pCurLex.pType is LexType.comment and self.pCurLex.pVal.startswith("#:"):
                cc = self.pCurLex.pVal[2:]
                cmd, args = cc.strip().split(" ", 1)
                if cmd == "set":
                    key, value = args.split(" ", 1)
                    assert key in self.pParams
                    value = (type(self.pParams[key]))(value)
                    self.pParams[key] = value
                else:
                    assert False
            self.nextLex()
    
    def parseSheets(self):
        duration = 0
        while self.pCurLex.pType in (LexType.note, LexType.bracketOpen, LexType.space, LexType.comment):
            if self.pCurLex.pType in (LexType.note, LexType.bracketOpen):
                duration += self.parseNote()
            else:
                self.nextLex()
        return duration
    
    def parseNote(self):
        duration = 0
        if self.pCurLex.pType is LexType.note:
            if not self.pCurLex.pVal.isPause():
                self.pSheets.append((self.pTick, self.pCurLex.pVal))
            self.pTick += self.pCurLex.pVal.duration
            self.pMaxDuration = max(self.pMaxDuration, self.pTick + self.pCurLex.pVal.duration)
            duration += self.pCurLex.pVal.duration
        elif self.pCurLex.pType is LexType.bracketOpen:
            self.nextLex()
            duration += self.parseSheets()
            assert self.pCurLex.pType is LexType.bracketClose
        else:
            assert False
        self.nextLex()
        if self.pCurLex.pType is LexType.dash:
            self.nextLex()
            self.pTick -= duration
            self.duration = 0
        return duration
            