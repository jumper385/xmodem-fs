#!/usr/bin/env python3
"""
Simple XMODEM receiver for testing purposes.
Run this on the receiving side to test the XMODEM sender.
"""

import argparse
import sys
import time
import serial
from xmodem import XMODEM, XMODEM1k

def make_receiver_modem(ser, use_1k=False, debug=False):
    """Create receiver modem"""
    def getc(size, timeout=1):
        ser.timeout = timeout
        data = ser.read(size)
        if debug and data:
            print(f"RX DEBUG: Received {len(data)} bytes: {data.hex()}", file=sys.stderr)
        return data if data else None

    def putc(data, timeout=1):
        ser.write_timeout = timeout
        if debug:
            print(f"RX DEBUG: Sending {len(data)} bytes: {data.hex()}", file=sys.stderr)
        written = ser.write(data)
        ser.flush()
        return written

    return (XMODEM1k if use_1k else XMODEM)(getc, putc)

def test_receiver(port, baud, output_file, use_1k=False, debug=False, timeout=3.0):
    """Test XMODEM receiver"""
    try:
        ser = serial.Serial(
            port=port,
            baudrate=baud,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=timeout,
            write_timeout=timeout,
        )
        
        print(f"XMODEM Receiver started on {port} at {baud} baud")
        print(f"Saving to: {output_file}")
        print(f"Mode: {'XMODEM-1k' if use_1k else 'XMODEM'}")
        print("Waiting for sender to start transmission...")
        
        modem = make_receiver_modem(ser, use_1k, debug)
        
        with open(output_file, 'wb') as f:
            received = modem.recv(f, retry=30, timeout=int(timeout))
            
        if received:
            print(f"\nReceive successful! File saved as: {output_file}")
            return True
        else:
            print(f"\nReceive failed!")
            return False
            
    except serial.SerialException as e:
        print(f"Serial error: {e}")
        return False
    except KeyboardInterrupt:
        print("\nReceive interrupted by user")
        return False
    except Exception as e:
        print(f"Error: {e}")
        return False
    finally:
        try:
            ser.close()
        except:
            pass

def main():
    parser = argparse.ArgumentParser(description="XMODEM Test Receiver")
    parser.add_argument("--port", "-p", required=True, help="Serial port")
    parser.add_argument("--baud", "-b", type=int, default=115200, help="Baud rate")
    parser.add_argument("--output", "-o", default="received_file.bin", help="Output file")
    parser.add_argument("--1k", action="store_true", help="Use XMODEM-1k")
    parser.add_argument("--debug", action="store_true", help="Enable debug output")
    parser.add_argument("--timeout", type=float, default=3.0, help="Timeout in seconds")
    
    args = parser.parse_args()
    
    success = test_receiver(
        args.port, 
        args.baud, 
        args.output, 
        args.x1k, 
        args.debug, 
        args.timeout
    )
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()