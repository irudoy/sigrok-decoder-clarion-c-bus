'''
* SDA - Data, Open-collector, 5V, driven by changer and head, pulled up by head 
* SCL - 5V, driven by head, clocks data on SDA. Data changes at falling edge, may be sampled on rising edge. 
* SRQ - Open-collector, 5V, driven by changer, pulled up by head. active-low requests the head to poll the changer 

This section describes the bitwise protocol used for the lowest level of data transfer. This could best be done with a clocked serial port, but the timing doesn't seem too critical and I've been able to emulate serial port hardware using a microcontroller capable of an interrupt response in about 2us (and repeated every 7us). 

Most of the action takes place on the SCK (clock) and SDA (data) lines. The head unit is always the clock master, but the data line is passively pulled up by the head unit and may be pulled down by an open-collector driver in the changer. In the changer I looked at, this open-collector driver is outside the microcontroller used for the serial port, and the control of the output driver is handled via a different pin to that used to read the state of the line. Although it would normally be difficult to determine which end was controlling the bidirectional data line (and hence which guay the data was flowing), picking up these lines separately meant I could determine which end was asserting zero data (clock the data from both lines into separate receivers : when the values are equal, the changer is sending data. When they're different, the head is sending). This is still ambiguous when all-ones are sent, but this only occurs within the data packets described later - no commands have the value FF as far as I can tell. If they did, the context of surrounding commands would probably indicate the direction but I think FF is specifically banned as it would be impossible to determine whether the changer had echoed it or was missing. 

The clock and data lines both rest at 5V, and the data line normally changes only on a falling edge of the clock (regardless of whether the head or changer are driving it). However, when the head is trying to re-establish communication with the changer (at power-up or after a protocol error) it will hold the clock high while cycling the data line. This is similar to part of a synchronous serial protocol supported by the NEC microcontroller used in this changer, and although that protocol doesn't seem to be used for the data handshake, I think it's a deliberate violation used here to indicate that a bus reset should be performed. In the NEC controller, the violation is simply that the data line changes while the clock is low, but this is sensitive to noise and poorly-propagated signals on the long cable between head and boot-mounted changer. It's probably OK to implement this reset more conveniently by detecting a relatively long period during which the data line is low, and when no clock edges are seen. 


Each byte referred to in later sections is transferred in a distinct burst of clocks. This burst typically lasts about 2ms (though it could vary widely) and there's usually a 2ms rest before another burst occurs. Therefore, the bus only transfers about 1 byte every 4ms and so is equivalent to about 2400 baud if no flowcontrol information were required. The clocks themselves are very regular with a duty cycle close to 50% and a period of just over 7us. 

Data is transferred on the first 8 clocks of the burst, and I've assumed most significant bit is sent first in the descriptions below (this seems to be reasonable given that numeric values such as track numbers tie up as expected .. not bit-reversed). The first edge of the clock burst is obviously falling, so this can be used to shift the most significant data bit onto SDA. It's value is then available in time to be sampled by the receiver on the rising edge. 

After the first 8 clocks, the data line stays high while several hundred more clocks occur. This seems to hold the head off for as long as the changer wants, though there may be a maximum permitted time. Towards the end of the clock burst, the data line goes low, again for a variable (but short) number of clocks - sometimes as few as 1 - and finally goes high. The head stops clocking after receiving that final 1, and the transfer is complete. 

The actual number of clocks in high and low handshake states could be significant, and is fairly repeatable on the measurements I made. However, I hoped that it's irrelevant and indicated only how long the changer took to process the command. This seems correct, as the protocol seems to work correctly even in my implementation where the number of clocks in the handshake are always the same. 

It's possible that the handshake could be made faster by reducing the number of busy clocks per byte. However, this might outrun the head unit's ability to read response data and I haven't experimented with this .. I've used about 148 high clocks or 1.3ms followed by 3 low clocks.

Byte protocol 
=============

The commands and responses in the next section are presented as <Cmd> and a variable length response. Actually, it's a bit more verbose - this syntax is summarised to make it easier to read. 

All serial commands are initiated by the head unit and consist of a command byte transmitted to the changer, a response byte from the changer, and then some optional further data. In almost every case, the initial response byte is an echo of the command byte and is followed by a short message. This message is formatted as <length> <data> <data> ... where <length> is the count of bytes following. A zero length message is quite common, and consists only of the length zero. 

Each byte of the message (including the length) is actually sent twice, the second occurrence being the complement of the first. Thus the message in the example listed below as 

<Cmd> <Rlen> 00 01 00 

is actually transmitted as 

09 command from head to changer 
09 echo from changer to head 
03 length from changer 
FC complement of length from changer 
00 first data byte from changer 
FF complement of first data byte from changer 
01 second data byte from changer 
FE complement of second data byte from changer 
00 third data byte from changer 
FF complement of first data byte from changer 

There are a couple of exceptions to this format, related to an interrupt mechanism. 

This mechanism uses an additional line in the cable for the changer to request service by the head unit. The line (SRQ) is pulled to ground and the head unit then issues a command 00. 00 is not echoed - instead, the changer sends F7 on all occasions I've logged. Given the line protocol it would be possible for multiple units to modify this value, so it's possible that clearing a single bit in the response to 00 is really a response indicating a single station requesting service (this would be similar to a parallel poll in the IEEE-488 protocol). 

The head unit then sends F7. This command is echoed normally, but there's no additional message : not even a 00 length byte. The SRQ line is released at this time. So the sequence appears to be that the changer requests service with SRQ, is polled with 00 and has the service request acknowledged with F7. 

After the SRQ handshake is complete, the head always sends <Cmd>. This operates as a normal command (it results in the usual length-and-data response) but the actual contents of the response vary rather more widely than do most of the other responses logged, and have a variety of effects on the head unit. Some change the track/time display, one enables the audio from the changer, etc. <Cmd> therefore appears to be a higher-level poll from the head (made in response to a succesful SRQ) that permits the changer to send the head an 'unsolicited' message. This is particularly noticeable in the '10 xx yy' response mentioned below - every second, the changer performs an SRQ and sends 10 xx yy in response to the <Cmd>. This results in the head updating its display to show xx minutes and yy seconds on the track progress display. The first byte of the response to <Cmd> can probably be considered as a command to the head, rather than data as in a normal response. 

Thus the message listed later as 

<SRQ> <Cmd> <Rlen> 32 01 

is actually transmitted as 

SRQ goes low 
00 command from head to changer 
F7 response from changer to head 
F7 command from head to changer 
SRQ rises 
F7 echo from changer to head 
11 command from head to changer 
11 echo from changer to head 
02 length from changer 
FD complement of length from changer 
32 first data byte from changer 
CD complement of first data byte from changer 
01 second data byte from changer 
FE complement of second data byte from changer 

F7 is also sent as part of the powerup / reset sequence and again is only echoed, there's no command tail. In this case, no <Cmd> follows F7. 

If this protocol fails (a transfer times out, or a command is echoed inaccurately, or true/complement data doesn't match) the head will sometimes retry the command and if unsuccessful fall back to resetting the bus using the F7 command. It then carries on with the command sequence in progress. It doesn't normally start from scratch just to repair a protocol failure, but if the changer doesn't respond to the protocol reset the head will give up, reporting 'CONNECT' on the display. Re-selecting the changer from the head unit front panel will start the reset sequence up from scratch - it isn't necessary to power cycle for the head unit to recognise that a changer is present. 

At powerup, there's another possible variation. If the head fails to get a sensible response from the changer (it has about 4 attempts to send F7, and if the changer isn't present will receive FF in response due to the lack of any active pulldown), it will try 7D instead (again for 4 attempts). The safest response to this is FF, which looks like a not-present. The head will then (perhaps on another occasion) send F7 and the protocol described can then be followed. My guess is that this head unit is willing to talk to at least two distinct changer units and attempts to find the right protocol by attempting a different reset message. There's some need for experimentation here to see if this or another changer will accept the 7D command, and what the head unit will do if it's accepted.

http://embedded-bg.com/clarion_c-bus.txt
'''

from .pd import Decoder
