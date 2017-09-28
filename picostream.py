# Picoscope streaming in Python; link AWG output to channel A input
# Tested with 2406B scope, 32-bit PicoSDK 10.6.12, Windows Python 2.6.6, 2.7.9 and 3.5.3
# Pure Python; if PLOT_DATA is false, requires no extra packages
# 
# Created by Jeremy Bentham Iosoft Ltd. September 2017
# Released under Creative Commons Attribution 4.0 International Public License
# 
# v0.01 JPB 20/9/17  First version: callback not working
# v0.02 JPB 20/9/17  Added DLL wrapper option
#                    (same result, with occasional error 27h on GetStreamingLatestValues)
# v0.03 JPB 21/9/17  Tidied up wrapper function calls
# v0.04 JPB 21/9/17  Got callback working, removed wrapper code
# v0.05 JPB 21/9/17  Removed auto-stop, added streaming timeout
# v0.06 JPB 21/9/17  Added data aggregation and plotting
# v0.07 JPB 22/9/17  Fixed data dropouts under Python 3

from __future__ import print_function
from ctypes import *
import time, sys

# DLL interface defined in picoscope-2000-series-a-api-programmers-guide.pdf
pico_dll          = windll.ps2000a
SCOPE_TYPE        = "ps2000a"

BUFFLEN         = 100000  # Length of scope buffer (samples)
DATALEN         = 500000  # Length of data to be streamed (samples)
SAMPLE_TIME_US  = 1       # Sample time (microseconds)
STREAM_TIMEOUT  = 5       # Timeout for streaming (seconds)
GETVALUES_DELAY = 0.002   # Delay between calls to get data (seconds)
PLOT_DATA       = True    # Enable plotting of data (requires matplotlib)

SIG_GEN_FREQ    = 5       # Frequency of signal generator (Hz)
SIG_GEN_AMP     = 2.0     # Amplitude of signal generator (V p-p)
SIG_GEN         = True    # Enable signal generator output

# Constants from ps2000aApi.h
CHAN_A            = 0
ENABLE            = 1
COUPLING_DC       = 1
RANGE_2V          = 7
OFFSET            = c_float(0.0)
SEG_INDEX         = 0
RATIO_MODE_NONE   = 0
SAMP_INTERVAL     = c_int(SAMPLE_TIME_US)
SAMP_US           = 3
PRE_TRIG          = 0
POST_TRIG         = 10000
NO_AUTOSTOP       = 0
DOWNSAMP_RATIO    = 1
CALLBACK_PARAM    = c_void_p()
# Signal generator
SIG_OFFSET        = 0
SIG_WAVE_SINE     = 0
SIG_FREQ_INCR     = c_float(0.0)
SIG_DWELL_TIME    = c_float(0.0)
SIG_SWEEP_UP      = 0
SIG_EXTRA_OFF     = 0
SIG_SHOTS         = 0
SIG_SWEEPS        = 0
SIG_TRIG_RISING   = 0
SIG_TRIG_NONE     = 0
SIG_TRIG_THRESH   = c_int16(0)

pscope = c_int16(0)                 # Scope handle
scope_buffer = (c_short*BUFFLEN)(0) # Buffer used by driver
data_buffer = (c_short*(DATALEN))(0)# Buffer for accumulated data
called_back = False                 # Flag set by callback
sample_count = 0                    # Total samples received    
block_offset = 0                    # Start position of latest block in buffer
block_samples = 0                   # Number of samples in latest block

# Call the Pico DLL with a method and args; if return is non-zero, close and exit
def pico(method, args):
    m = getattr(pico_dll, SCOPE_TYPE+method)
    retval = m(*args)
    if retval:
        print("Error %Xh: %s" % (retval, method))
        if args[0]:
            m = getattr(pico_dll, SCOPE_TYPE+"CloseUnit")
            m(args[0])
        sys.exit()

# Enable the signal generator, given wavetype, frequency and amplitude (volts P-P)
def pico_sig_gen(h, wave, freq, amp):
    pico("SetSigGenBuiltIn", (h, SIG_OFFSET, int(amp*1.0e6), wave, c_float(freq), c_float(freq),
                              SIG_FREQ_INCR, SIG_DWELL_TIME, SIG_SWEEP_UP, SIG_EXTRA_OFF, 
                              SIG_SHOTS, SIG_SWEEPS, SIG_TRIG_RISING, SIG_TRIG_NONE, SIG_TRIG_THRESH))

# Callback when data block has arrived
@WINFUNCTYPE(None, c_int16, c_int32,  c_uint32, c_int16,  c_uint32,  c_int16,   c_int16,  c_int32)
def callback_py(   handle,  nSamples, startIdx, overflow, triggerAt, triggered, autoStop, param):
    # Update global variables
    global block_offset, block_samples, sample_count, called_back
    block_offset, block_samples = startIdx, nSamples
    # Copy new block into my data buffer using ctypes functions (a sample is 2 bytes)
    srce_addr = addressof(scope_buffer) + block_offset*2
    dest_addr = addressof(data_buffer) + sample_count*2
    memmove(dest_addr, srce_addr, block_samples*2)
    sample_count += block_samples
    called_back = True

if __name__ == '__main__':
    print("Opening Picoscope %s... " % SCOPE_TYPE, end='')
    pico("OpenUnit", (byref(pscope), None))
    print("OK")

    # Enable signal generator
    if SIG_GEN:
        pico_sig_gen(pscope, SIG_WAVE_SINE, SIG_GEN_FREQ, SIG_GEN_AMP) 
    
    # Prepare for streaming
    pico("SetChannel", (pscope, CHAN_A, ENABLE, COUPLING_DC, RANGE_2V, OFFSET))
    pico("SetDataBuffer", (pscope, CHAN_A, byref(scope_buffer), BUFFLEN, SEG_INDEX, RATIO_MODE_NONE))
    pico("RunStreaming", (pscope, byref(SAMP_INTERVAL), SAMP_US, PRE_TRIG, POST_TRIG, NO_AUTOSTOP, DOWNSAMP_RATIO, RATIO_MODE_NONE, BUFFLEN))

    # Streaming loop, with a timeout in case the streaming stalls
    # Keep requesting data using GetStreamingLatestValues, which generates a callback for each block
    # The block is generally smaller than the buffer size, so the DLL appends it to the scope buffer.
    # When the scope buffer is full, the driver wraps around and overwrites the data at address 0
    # The callback copies each incoming block to my data buffer, so this loop doesn't do much
    startime = time.time()
    while sample_count<DATALEN and time.time()-startime < STREAM_TIMEOUT:
        if called_back:
            called_back = False
            print('Callback: %5u samples at %u' % (block_samples, block_offset))
        time.sleep(GETVALUES_DELAY)
        pico("GetStreamingLatestValues", (pscope, callback_py, byref(CALLBACK_PARAM)))

    # Tidy up
    pico("Stop", (pscope,))
    pico("CloseUnit", (pscope,))

    # Print or plot the data
    if not PLOT_DATA:
        for i in range(0, 10):
            print("%04X " % scope_buffer[0], end='')
        print()
    else:
        import matplotlib.pyplot as plt
        fig = plt.figure()
        xvals = [i*SAMPLE_TIME_US/1e6 for i in range(len(data_buffer))]
        plt.plot(xvals, data_buffer, 'b-', linewidth=0.5)
        plt.show()
# EOF

