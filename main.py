import wave, audioop, math, struct
import parser


class WavData:
    def __init__(self, framerate=44100):
        self.framerate = framerate
        self.data = []
    
    @staticmethod
    def open(fname):
        ifile = wave.open(fname, "r")
        assert ifile.getnchannels() == 1
        assert ifile.getsampwidth() == 2
        res = WavData(framerate=ifile.getframerate())
        data = [struct.unpack("h", ifile.readframes(2)) / 32767 for _ in range(ifile.getnframes())]
        res.write(data)
        ifile.close()
        return res
    
    def save(self, fname):
        ofile = wave.open(fname, "w")
        ofile.setnchannels(1)
        ofile.setsampwidth(2)
        ofile.setframerate(self.framerate)
        ofile.writeframes(self.encodeFrames())
        ofile.close()
    
    def encodeFrame(self, frame):
        assert isinstance(frame, (int, float))
        assert -1 <= frame <= 1
        val = int(frame * 32767)
        return struct.pack("h", val)
    
    def encodeFrames(self):
        res = bytearray()
        for frame in self.data:
            res.extend(self.encodeFrame(frame))
        return res
    
    def writeFrame(self, data):
        assert isinstance(data, (int, float))
        self.data.append(data)
    
    def write(self, data):
        for frame in data:
            self.writeFrame(frame)
    
    def adjust(self, coef):
        self.data = list(map(lambda x: x * coef, self.data))
    
    def normalize(self):
        ampl = max(map(abs, self.data))
        if ampl != 0:
            self.adjust(1 / ampl)


class AudioController:
    def __init__(self, duration, framerate=44100):
        self.duration = duration
        self.framerate = framerate
        self.elements = set()
    
    def addElement(self, offset, element):
        self.elements.add((offset, element))
    
    def getWavData(self):
        wd = WavData(self.framerate)
        i = 0
        elements = sorted(self.elements, key=lambda x: x[0])
        activeElements = set()
        for frame in range(int(self.duration * self.framerate)):
            time = frame / self.framerate
            while i < len(elements) and elements[i][0] <= time:
                activeElements.add(elements[i])
                i += 1
            val = 0
            expired = set()
            for offset, elem in activeElements:
                if offset + elem.getDuration() < time:
                    expired.add((offset, elem))
                    continue
                val += elem.getValue(time - offset)
            activeElements -= expired
            wd.writeFrame(val)
        return wd


class AudioElement:
    def getDuration(self):
        raise NotImplementedError()
    
    def getValue(self, time):
        raise NotImplementedError()


class HarmonicElement(AudioElement):
    def __init__(self, freq, amp, duration, loss=lambda elem, time: 1):
        self.freq = freq
        self.amp = amp
        self.duration = duration
        self.loss = loss
    
    def getDuration(self):
        if hasattr(self.loss, "getDuration"):
            return self.loss.getDuration(self)
        return self.duration
    
    def getValue(self, time):
        return self.amp * math.sin(2 * math.pi * self.freq * time) * self.loss(self, time)


class CombinedElement(AudioElement):
    def __init__(self, freq, amp, duration, loss=lambda elem, time: 1):
        self.freq = freq
        self.amp = amp
        self.loss = loss
        self.duration = duration
        self.populateElements()
        self.duration = max([x.getDuration() for x in self.elements])
    
    def populateElements(self):
        self.elements = []
        raise NotImplementedError()
    
    def getDuration(self):
        return self.duration
    
    def getValue(self, time):
        return sum(map(lambda x: x.getValue(time), self.elements))


class OrganElement(CombinedElement):
    def populateElements(self):
        self.elements = [HarmonicElement(self.freq, self.amp, self.duration, self.loss), HarmonicElement(self.freq * 1.5, self.amp * 0.2, self.duration, self.loss)]


def sqrtLoss(elem, time):
    return (1 - time / elem.duration) ** 0.5


def expLoss(elem, time):
    return math.exp(time / (elem.freq / 50 * (time - elem.duration)))


class ADSRLoss:
    def __init__(self, ampA, ampD, ampR, timeA, timeD, timeR):
        self.ampA = ampA
        self.ampD = ampD
        self.ampR = ampR
        self.timeA = timeA
        self.timeD = timeD
        self.timeR = timeR
    
    def __call__(self, elem, time):
        dur = self.getDuration(elem)
        if 0 <= time < self.timeA:
            return (self.ampA * (self.timeA - time) + self.ampD * time) / self.timeA
        if self.timeA <= time < self.timeD:
            return (self.ampD - self.ampR) * ((time - self.timeA) / (self.timeD - self.timeA) - 1) ** 2 + self.ampR
        if self.timeD <= time < dur - self.timeR:
            return self.ampR
        if dur - self.timeR <= time < dur:
            return (self.ampR) * ((time - (dur - self.timeR)) / (self.timeR) - 1) ** 2
        return 0
    
    def getDuration(self, elem):
        return self.timeA + self.timeD + elem.duration + self.timeR


print("Starting...")
ac = AudioController(5)

#for n in range(10):
    #ac.addElement(0, HarmonicElement(220 * 2**n/(2*math.pi), 1/2**n, 4))

loss = ADSRLoss(1, 0.8, 0.3, 0.3, 0.25, 0.02)
ac.addElement(0, HarmonicElement(440, 1, 3, loss))
ac.addElement(1.3, HarmonicElement(440 * pow(2, -3 / 12), 0.5, 4, loss))

#ac.addElement(0, OrganElement(440 * pow(2, 0 / 12), 1, 1, loss))
#ac.addElement(0, OrganElement(440 * pow(2, -3 / 12), 1, 1, loss))
#ac.addElement(0, OrganElement(440 * pow(2, -7 / 12), 1, 1, loss))

print("Saving to 'out.wav'...")
wd = ac.getWavData()
wd.normalize()
wd.adjust(0.9)
wd.save("out.wav")
print("Done.")
