#!/usr/bin/env python3
"""
Serial communication test utility for diagnosing XMODEM issues.
Use this to test basic serial communication before attempting XMODEM transfers.
"""

import argparse
import time
import serial
import sys

def test_serial_connection(port, baud, timeout=3.0):
    """Test basic serial connection and communication."""
    print(f"Testing serial connection on {port} at {baud} baud...")
    
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
        
        print(f"✓ Serial port opened successfully")
        print(f"  Port: {ser.name}")
        print(f"  Baudrate: {ser.baudrate}")
        print(f"  Timeout: {ser.timeout}")
        print(f"  Write timeout: {ser.write_timeout}")
        
        # Clear buffers
        ser.reset_input_buffer()
        ser.reset_output_buffer()
        
        # Test basic communication
        print("\nTesting basic communication...")
        
        # Check if any data is waiting
        waiting = ser.in_waiting
        if waiting > 0:
            print(f"  Found {waiting} bytes in input buffer")
            data = ser.read(waiting)
            print(f"  Data: {data.hex()} ({data})")
        else:
            print(f"  No data in input buffer")
        
        # Send a test byte and see if anything comes back
        print("\nSending test bytes (0x01, 0x02, 0x03)...")
        test_bytes = b'\x01\x02\x03'
        ser.write(test_bytes)
        ser.flush()
        
        # Wait for response
        time.sleep(0.5)
        response = ser.read(10)  # Read up to 10 bytes
        
        if response:
            print(f"  Received response: {response.hex()} ({response})")
        else:
            print(f"  No response received")
        
        # Test XMODEM handshake characters
        print("\nTesting XMODEM control characters...")
        
        # NAK (0x15) - used by receiver to request transmission start
        print("  Sending NAK (0x15)...")
        ser.write(b'\x15')
        ser.flush()
        time.sleep(0.2)
        
        response = ser.read(10)
        if response:
            print(f"    Response to NAK: {response.hex()}")
        else:
            print(f"    No response to NAK")
        
        # C (0x43) - used for CRC mode
        print("  Sending C (0x43) for CRC mode...")
        ser.write(b'\x43')
        ser.flush()
        time.sleep(0.2)
        
        response = ser.read(10)
        if response:
            print(f"    Response to C: {response.hex()}")
        else:
            print(f"    No response to C")
        
        ser.close()
        print("\n✓ Serial test completed successfully")
        return True
        
    except serial.SerialException as e:
        print(f"✗ Serial error: {e}")
        return False
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        return False

def monitor_serial(port, baud, timeout=1.0):
    """Monitor serial port for incoming data."""
    print(f"Monitoring {port} at {baud} baud (Press Ctrl+C to stop)...")
    
    try:
        ser = serial.Serial(
            port=port,
            baudrate=baud,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=timeout,
        )
        
        while True:
            if ser.in_waiting > 0:
                data = ser.read(ser.in_waiting)
                timestamp = time.strftime("%H:%M:%S.%f")[:-3]
                print(f"[{timestamp}] Received {len(data)} bytes: {data.hex()} ({data})")
            time.sleep(0.1)
            
    except KeyboardInterrupt:
        print("\nMonitoring stopped.")
    except serial.SerialException as e:
        print(f"Serial error: {e}")
    finally:
        try:
            ser.close()
        except:
            pass

def main():
    parser = argparse.ArgumentParser(description="Serial communication test utility")
    parser.add_argument("--port", "-p", required=True, help="Serial port to test")
    parser.add_argument("--baud", "-b", type=int, default=115200, help="Baud rate (default: 115200)")
    parser.add_argument("--timeout", type=float, default=3.0, help="Timeout in seconds (default: 3.0)")
    parser.add_argument("--monitor", action="store_true", help="Monitor port for incoming data")
    
    args = parser.parse_args()
    
    if args.monitor:
        monitor_serial(args.port, args.baud, args.timeout)
    else:
        test_serial_connection(args.port, args.baud, args.timeout)

if __name__ == "__main__":
    main()