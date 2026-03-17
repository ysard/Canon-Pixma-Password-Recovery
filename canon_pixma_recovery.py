#!/usr/bin/env python3
# coding: utf-8
# Canon Pixma Password Recovery - A project to extract sensitive information
# from EEPROMs of Canon Pixma TS3100 series / TS3150 (at least) printers.
# Copyright (C) 2026  Ysard
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""Proof of concept for sensitive data recovery from the EEPROM
of Canon Pixma TS3100 series / TS3150 printers.

Use the following command to read the EEPROM with a CH341 USB adapter:

    $ flashrom -p ch341a_spi --progress -c "W25Q64JV-.Q" -r W25Q64JVSIQ.bin

Usage:

    $ python canon_pixma_password_recovery.py my_eeprom_dump.bin
"""
import sys
from pathlib import Path

# Keys: Chapter in the printed configuration page (if available), ID
# Values: List of tuples with offsets and one value of the following meanings:
# - 0: Expect null terminated string
# - None: Expect the 1st byte is the number of bytes that will be read
# - Numeric value: Number of bytes that will be read
DATA = {
    ("1.1.", "PRODUCT_NAME"): [(0x00009050, 0), (0x007FFB50, 0)],
    ("1.3.", "SERIAL_NB"): [
        (0x0000007C, 0),
        (0x0000107C, 0),
        (0x0001007C, 0),
        (0x0002007C, 0),
    ],
    ("3.2.4.", "MAC_ADDR"): [
        (0x0000605B, 12),
        (0x0001505B, 12),
        (0x0001605B, 12),
        (0x0001705B, 12),
        (0x0002605B, 12),
        (0x0002705B, 12),
    ],
    ("3.2.12.", "IP_ADDR"): [
        (0x00006097, None),
        (0x00016097, None),
        (0x00017868, 0),
        (0x00027868, 0),
    ],
    ("", "NETWORK_NAME"): [
        (0x00017097, None),
        (0x00017A04, 0),
        (0x00027097, None),
        (0x00027A04, 0),
    ],
    ("3.2.6.", "AP_ESSID"): [
        (0x000114A7, None),
        (0x000115B4, None),
        (0x000214A7, None),
        (0x000215B4, None),
    ],
    ("", "AP_PASSWORD"): [
        (0x00011543, 0),
        (0x000115DB, None),
        (0x00021543, 0),
        (0x000215DB, None),
    ],
    ("3.3.3.", "DIRECT_ESSID"): [(0x00011934, None), (0x00021934, None)],
    ("3.3.4.", "DIRECT_PASS"): [(0x00011958, 0), (0x00021958, 0)],
    ("3.3.9.", "DIRECT_IP_ADDR"): [
        (0x000178B2, 0),
        (0x00026097, None),
        (0x000278B2, 0),
    ],
    ("5.1.", "PRINTER_NAME"): [(0x00011A54, 0), (0x00021A54, 0)],
}


def read_until_null(f_d) -> bytes:
    """Search a null terminated string at the current position

    :raises ValueError: If no NULL char is found.
    :param f_d: File descriptor on the opened file.
    :type f_d: io.TextIOWrapper
    """
    text = bytes()
    while char := f_d.read(1):
        if char == b"\x00":
            return text.decode()
        text += char

    raise ValueError("NULL char was not found")


def extract_multi_pos(f_d, positions, debug=False) -> str:
    """Get the text values expected at the given positions

    :param f_d: File descriptor on the opened file.
    :param positions: List of offsets and lengths.
    :key debug: Enable debugging (show raw bytes).
    :type f_d: io.TextIOWrapper
    :type debug: bool
    """
    text_entries = set()
    for pos, length in positions:
        # print(pos)
        f_d.seek(pos)
        if length == 0:
            # Search null terminated string
            text = read_until_null(f_d)
            text_entries.add(text)
            continue

        if length is None:
            # Length is at the 1st byte of the current position
            length = int.from_bytes(f_d.read(1), byteorder="big")

        # Length of data is known
        data = f_d.read(length)
        if debug:
            print(data, data.decode())

        text_entries.add(data.decode())

    return ", ".join(text_entries)


def extractor(f_d, debug=False):
    """Extract and show the fields from the dump

    :param f_d: File descriptor on the opened file.
    :key debug: Enable debugging (show raw bytes).
    :type f_d: io.TextIOWrapper
    :type debug: bool
    """
    data = {
        key: extract_multi_pos(f_d, positions, debug=debug)
        for key, positions in DATA.items()
        if positions
    }

    for (chapter, name), text in data.items():
        if name == "DIRECT_PASS" and not text:
            # Password is not set: use the default value (serial number)
            text = data[("1.3.", "SERIAL_NB")]
        elif name == "PRINTER_NAME" and not text:
            # Printer name is not set: use the default value
            text = data[("", "NETWORK_NAME")].split(".")[0]

        print(f"{chapter} {name}: {text}")


def main(filepath, debug=False):
    """Process the given file

    :param filepath: Filepath of the eeprom dump.
    :key debug: Enable debugging (show raw bytes).
    :type filepath: pathlib.Path
    :type debug: bool
    """
    print("File:", filepath)

    with open(filepath, "rb") as f_d:
        extractor(f_d, debug=debug)


if __name__ == "__main__":

    if len(sys.argv) < 2:
        print("Forgot the file to open?")
        raise SystemExit

    filepath = Path(sys.argv[1])
    if not filepath.exists():
        print("Failed to open the file!")
        raise SystemExit

    main(filepath, debug=False)
