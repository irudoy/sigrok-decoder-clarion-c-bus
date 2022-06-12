import sigrokdecode as srd

class Signal:
    LOW = 'l' # Low pin value (logical 0)
    HIGH = 'h' # High pin value (logical 1)
    RISING = 'r' # Rising edge
    FALLING = 'f' # Falling edge
    EITHER = 'e' # Either edge (rising or falling)
    STABLE = 's' # Stable state, the opposite of 'e'. That is, there was no edge and the current and previous pin value were both low (or both high).

class Pin:
    (SCL, SDA, SRQ) = range(3)

class Annotation:
    (BITS, BYTES, SRQ) = range(3)

class Decoder(srd.Decoder):
    api_version = 3
    id = 'clarioncbus'
    name = 'C-Bus'
    longname = 'Clarion C-Bus'
    desc = 'C-Bus protocol used to communicate between a Clarion tuner/tape head unit and a remote CD changer'
    license = 'mit'
    inputs = ['logic']
    outputs = ['clarioncbus']
    tags = []
    channels = (
        {'id': 'scl', 'name': 'SCL', 'desc': 'Clock'},
        {'id': 'sda', 'name': 'SDA', 'desc': 'Data'},
        {'id': 'srq', 'name': 'SRQ', 'desc': 'Request for service'},
    )
    annotations = (
        ('data-bits', 'Data bits'),
        ('data-bytes', 'Data bytes'),
        ('srq', 'Request for service'),
    )
    annotation_rows = (
        ('data-bits', 'Bits', (Annotation.BITS,)),
        ('data-bytes', 'Bytes', (Annotation.BYTES,)),
        ('srq', 'SRQ', (Annotation.SRQ,)),
    )

    def __init__(self):
        self.reset()

    def reset(self):
        self.last_sample_num = 0
        self.prev_sample_num = 0
        self.bytestart = 0
        self.bitcount = 0
        self.byte = 0

    def start(self):
        self.out_ann = self.register(srd.OUTPUT_ANN)

    def metadata(self, key, value):
        if key == srd.SRD_CONF_SAMPLERATE:
            timeoutUs = 100
            self.timeout_samples_num = int((timeoutUs / 1000.0) * (value / 1000.0))

    def decode(self):
        while True:
            # wait for SCL falling
            self.wait([{ Pin.SCL: Signal.FALLING }])
            self.last_sample_num = self.samplenum

            # wait for SCL rising
            (scl, sdo, srq) = self.wait([{ Pin.SCL: Signal.RISING }])

            # check if prev_scl_rising_samples - scl_rising_samples < timeout
            sdiff = self.samplenum - self.prev_sample_num
            self.prev_sample_num = self.samplenum
            if sdiff > self.timeout_samples_num:
                self.bytestart = 0
                self.bitcount = 0
                self.byte = 0

            # add bit
            self.put(self.last_sample_num, self.samplenum, self.out_ann, [Annotation.BITS, ['Bit: %d' % sdo, '%d' % sdo]])

            # start of the byte
            if self.bitcount == 0:
                self.bytestart = self.last_sample_num

            # shift bit to byte
            self.byte |= sdo << (7 - self.bitcount)
            self.bitcount += 1

            if self.bitcount == 8:
                # add byte
                self.put(
                    self.bytestart,
                    self.samplenum,
                    self.out_ann,
                    [Annotation.BYTES, [
                        'Byte: 0x%(byte)02X (Dec: %(byte)d)' % {'byte': self.byte},
                        'Byte: 0x%02X' % self.byte,
                        '0x%02X' % self.byte,
                        '%02X' % self.byte
                    ]]
                )
                self.reset()
