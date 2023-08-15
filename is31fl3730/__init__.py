# SPDX-FileCopyrightText: 2017 Scott Shawcroft, written for Adafruit Industries
# SPDX-FileCopyrightText: Copyright (c) 2023 David Glaude
#
# SPDX-License-Identifier: MIT
"""
`public_circuitpython_is31fl3730`
================================================================================

CircuitPython driver for the IS31FL3730 charlieplex IC.


* Author(s): David Glaude

Implementation Notes
--------------------

**Hardware:**

.. todo:: Add links to any specific hardware product page(s), or category page(s).
  Use unordered list & hyperlink rST inline format: "* `Link Text <url>`_"

**Software and Dependencies:**

* Adafruit CircuitPython firmware for the supported boards:
  https://circuitpython.org/downloads

.. todo:: Uncomment or remove the Bus Device and/or the Register library dependencies
  based on the library's use of either.

# * Adafruit's Bus Device library: https://github.com/adafruit/Adafruit_CircuitPython_BusDevice
# * Adafruit's Register library: https://github.com/adafruit/Adafruit_CircuitPython_Register
"""

# imports
import math
import time
from micropython import const

from adafruit_bus_device.i2c_device import I2CDevice

__version__ = "0.0.0+auto.0"
__repo__ = (
    "https://github.com/dglaude/Public_CircuitPython_CircuitPython_IS31FL3730.git"
)

_SOME_REGISTER = const(0x00)


class IS31FL3730:
    """
    The IS31FL3730 is an abstract class contain the main function related to this chip.
    Each board needs to define width, height and pixel_addr.

    :param ~busio.I2C i2c: the connected i2c bus i2c_device
    :param int address: the device address; defaults to 0x61
    """

    width = 16
    height = 9

    #### Here stop the transformation from ISL31FL3731 to ISL31FL3730

    def __init__(self, i2c, address=0x74, frames=None):
        self.i2c_device = I2CDevice(i2c, address)
        self._frame = None
        self._init(frames=frames)

    def _i2c_read_reg(self, reg, result):
        # Read a buffer of data from the specified 8-bit I2C register address.
        # The provided result parameter will be filled to capacity with bytes
        # of data read from the register.
        with self.i2c_device as i2c:
            i2c.write_then_readinto(bytes([reg]), result)
            return result
        return None

    def _i2c_write_reg(self, reg, data):
        # Write a contiguous block of data (bytearray) starting at the
        # specified I2C register address (register passed as argument).
        self._i2c_write_block(bytes([reg]) + data)

    def _i2c_write_block(self, data):
        # Write a buffer of data (byte array) to the specified I2C register
        # address.
        with self.i2c_device as i2c:
            i2c.write(data)

    def _bank(self, bank=None):
        if bank is None:
            result = bytearray(1)
            return self._i2c_read_reg(_BANK_ADDRESS, result)[0]
        self._i2c_write_reg(_BANK_ADDRESS, bytearray([bank]))
        return None

    def _register(self, bank, register, value=None):
        self._bank(bank)
        if value is None:
            result = bytearray(1)
            return self._i2c_read_reg(register, result)[0]
        self._i2c_write_reg(register, bytearray([value]))
        return None

    def _mode(self, mode=None):
        return self._register(_CONFIG_BANK, _MODE_REGISTER, mode)

    def _init(self, frames=None):
        self.sleep(True)
        # Clear config; sets to Picture Mode, no audio sync, maintains sleep
        self._bank(_CONFIG_BANK)
        self._i2c_write_block(bytes([0] * 14))
        enable_data = bytes([_ENABLE_OFFSET] + [255] * 18)
        fill_data = bytearray([0] * 25)
        # Initialize requested frames, or all 8 if unspecified
        for frame in frames if frames else range(8):
            self._bank(frame)
            self._i2c_write_block(enable_data)  # Set all enable bits
            for row in range(6):  # Barebones quick fill() w/0
                fill_data[0] = _COLOR_OFFSET + row * 24
                self._i2c_write_block(fill_data)
        self._frame = 0  # To match config bytes above
        self.sleep(False)

    def reset(self):
        """Kill the display for 10MS"""
        self.sleep(True)
        time.sleep(0.01)  # 10 MS pause to reset.
        self.sleep(False)

    def sleep(self, value):
        """
        Set the Software Shutdown Register bit

        :param value: True to set software shutdown bit; False unset
        """
        return self._register(_CONFIG_BANK, _SHUTDOWN_REGISTER, not value)

    def audio_sync(self, value=None):
        """Set the audio sync feature register"""
        return self._register(_CONFIG_BANK, _AUDIOSYNC_REGISTER, value)

    def audio_play(self, sample_rate, audio_gain=0, agc_enable=False, agc_fast=False):
        """Controls the audio play feature"""
        if sample_rate == 0:
            self._mode(_PICTURE_MODE)
            return
        sample_rate //= 46
        if not 1 <= sample_rate <= 256:
            raise ValueError("Sample rate out of range")
        self._register(_CONFIG_BANK, _ADC_REGISTER, sample_rate % 256)
        audio_gain //= 3
        if not 0 <= audio_gain <= 7:
            raise ValueError("Audio gain out of range")
        self._register(
            _CONFIG_BANK,
            _GAIN_REGISTER,
            bool(agc_enable) << 3 | bool(agc_fast) << 4 | audio_gain,
        )
        self._mode(_AUDIOPLAY_MODE)

    def blink(self, rate=None):
        """Updates the blink register"""
        # pylint: disable=no-else-return
        # This needs to be refactored when it can be tested
        if rate is None:
            return (self._register(_CONFIG_BANK, _BLINK_REGISTER) & 0x07) * 270
        elif rate == 0:
            self._register(_CONFIG_BANK, _BLINK_REGISTER, 0x00)
            return None
        rate //= 270
        self._register(_CONFIG_BANK, _BLINK_REGISTER, rate & 0x07 | 0x08)
        return None

    def fill(self, color=None, blink=None, frame=None):
        """
        Fill the display with a brightness level

        :param color: brightness 0->255
        :param blink: True if blinking is required
        :param frame: which frame to fill 0->7
        """
        if frame is None:
            frame = self._frame
        self._bank(frame)
        if color is not None:
            if not 0 <= color <= 255:
                raise ValueError("Color out of range")
            data = bytearray([color] * 25)  # Extra byte at front for address.
            with self.i2c_device as i2c:
                for row in range(6):
                    data[0] = _COLOR_OFFSET + row * 24
                    i2c.write(data)
        if blink is not None:
            data = bool(blink) * 0xFF
            for col in range(18):
                self._register(frame, _BLINK_OFFSET + col, data)

    # This function must be replaced for each board
    @staticmethod
    def pixel_addr(x, y):
        """Calulate the offset into the device array for x,y pixel"""
        return x + y * 16

    # pylint: disable-msg=too-many-arguments
    def pixel(self, x, y, color=None, blink=None, frame=None):
        """
        Blink or brightness for x-, y-pixel

        :param x: horizontal pixel position
        :param y: vertical pixel position
        :param color: brightness value 0->255
        :param blink: True to blink
        :param frame: the frame to set the pixel
        """
        if not 0 <= x <= self.width:
            return None
        if not 0 <= y <= self.height:
            return None
        pixel = self.pixel_addr(x, y)
        if color is None and blink is None:
            return self._register(self._frame, pixel)
        if frame is None:
            frame = self._frame
        if color is not None:
            if not 0 <= color <= 255:
                raise ValueError("Color out of range")
            self._register(frame, _COLOR_OFFSET + pixel, color)
        if blink is not None:
            addr, bit = divmod(pixel, 8)
            bits = self._register(frame, _BLINK_OFFSET + addr)
            if blink:
                bits |= 1 << bit
            else:
                bits &= ~(1 << bit)
            self._register(frame, _BLINK_OFFSET + addr, bits)
        return None

    # pylint: enable-msg=too-many-arguments

    def image(self, img, blink=None, frame=None):
        """Set buffer to value of Python Imaging Library image.  The image should
        be in 8-bit mode (L) and a size equal to the display size.

        :param img: Python Imaging Library image
        :param blink: True to blink
        :param frame: the frame to set the image
        """
        if img.mode != "L":
            raise ValueError("Image must be in mode L.")
        imwidth, imheight = img.size
        if imwidth != self.width or imheight != self.height:
            raise ValueError(
                "Image must be same dimensions as display ({0}x{1}).".format(
                    self.width, self.height
                )
            )
        # Grab all the pixels from the image, faster than getpixel.
        pixels = img.load()

        # Iterate through the pixels
        for x in range(self.width):  # yes this double loop is slow,
            for y in range(self.height):  #  but these displays are small!
                self.pixel(x, y, pixels[(x, y)], blink=blink, frame=frame)
