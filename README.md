# picostream
picostream.py is a simple demonstration of data streaming from a Pico oscilloscope to a Windows PC using pure Python

It has been tested with a 2406B scope, 32-bit PicoSDK 10.6.12, Windows Python 2.6.6, 2.7.9 and 3.5.3

No installation required; just run the code from a convenient directory, with the AWG port connected to scope channel A.

The code sets up the AWG port to generate a sine wave, captures several blocks of data from input A, then plots them using matplotlib. Plotting can be disabled, in which case there are no package dependancies.

Data rate is 1 megasample/sec, which is a realistic maximum speed for a Python implementation. The upper limit is determined by the amount of processing that is done on the received data, and the rate of GetStreamingLatestValues calls; if called too frequently, this exits with error 27 hex (busy)

When adapting this code for your application, it is worth experimenting with the sample rate & time delay values, to see what works for you. I suspect that the occasional 'busy' errors from GetStreamingLatestValues can just be ignored, but have no cofirmation of that from Pico.

Jeremy Bentham September 2017

