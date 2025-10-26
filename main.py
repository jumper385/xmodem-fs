import argparse
import os
import sys
import time
import serial
from xmodem import XMODEM, XMODEM1k

def open_serial(port, baud, rtscts=False, dsrdtr=False, timeout=1.0):
    try:
        ser = serial.Serial(
            port=port,
            baudrate=baud,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=timeout,
            rtscts=rtscts,
            dsrdtr=dsrdtr,
            write_timeout=timeout,
            inter_byte_timeout=None,  # Ensure we don't timeout between bytes
            exclusive=True  # Prevent other processes from using the port
        )
        # Give the serial connection time to stabilize
        time.sleep(0.2)
        return ser
    except serial.SerialException as e:
        print(f"Failed to open serial port {port}: {e}", file=sys.stderr)
        sys.exit(1)

def make_modem(ser, use_1k: bool, debug=False, crc_mode=True):
    # xmodem expects two callables: getc(size, timeout) and putc(data, timeout)
    def getc(size, timeout=1):
        ser.timeout = timeout
        data = ser.read(size)
        if debug and data:
            print(f"DEBUG: Received {len(data)} bytes: {data.hex() if len(data) <= 10 else data[:10].hex() + '...'}", file=sys.stderr)
        return data if data else None

    def putc(data, timeout=1):
        ser.write_timeout = timeout
        if debug:
            print(f"DEBUG: Sending {len(data)} bytes: {data.hex() if len(data) <= 10 else data[:10].hex() + '...'}", file=sys.stderr)
        written = ser.write(data)
        ser.flush()
        # Increased delay for problematic receivers
        time.sleep(0.01)  # 10ms delay instead of 1ms
        return written

    # Create modem - always start with standard mode
    if use_1k:
        modem = XMODEM1k(getc, putc)
    else:
        modem = XMODEM(getc, putc)
    
    # Note: CRC mode is negotiated automatically by the xmodem library
    # based on receiver's initial character (C for CRC, NAK for checksum)
    if debug:
        print(f"DEBUG: Created {'XMODEM-1k' if use_1k else 'XMODEM'} modem, CRC preference: {crc_mode}", file=sys.stderr)
    
    return modem

def human(n):
    for unit in ["B","KB","MB","GB"]:
        if n < 1024.0:
            return f"{n:.1f} {unit}"
        n /= 1024.0
    return f"{n:.1f} TB"

def cmd_send(args):
    ser = open_serial(args.port, args.baud, args.rtscts, args.dsrdtr, args.timeout)
    fh = None
    try:
        # Add CRC mode option and pass to modem
        crc_mode = getattr(args, 'crc', True)  # Default to CRC mode
        modem = make_modem(ser, args.x1k, args.debug, crc_mode)

        # Clear buffers and wait for receiver to be ready
        ser.reset_input_buffer()
        ser.reset_output_buffer()
        time.sleep(1.0)  # Longer initial delay for problematic receivers
        
        # More aggressive buffer clearing
        for _ in range(3):  # Try multiple times
            while ser.in_waiting > 0:
                stale_data = ser.read(ser.in_waiting)
                if args.debug:
                    print(f"DEBUG: Drained {len(stale_data)} stale bytes: {stale_data.hex()}", file=sys.stderr)
                time.sleep(0.1)
            time.sleep(0.2)

        # Try to trigger receiver into XMODEM mode if it's not ready
        if args.debug:
            print("DEBUG: Attempting to wake up receiver...", file=sys.stderr)
        
        # Send some wake-up sequences that might help
        wake_sequences = [
            b'\r\n',  # Carriage return + line feed
            b'\x03',  # Ctrl+C to break out of any running program
            b'\r\n',  # Another CR+LF
        ]
        
        for seq in wake_sequences:
            ser.write(seq)
            ser.flush()
            time.sleep(0.2)
            # Clear any responses
            if ser.in_waiting > 0:
                response = ser.read(ser.in_waiting)
                if args.debug:
                    print(f"DEBUG: Wake-up response: {response.hex()}", file=sys.stderr)

        # Final buffer clear
        ser.reset_input_buffer()
        ser.reset_output_buffer()

        # Open the file to send
        size = os.path.getsize(args.file)
        fh = open(args.file, "rb")

        sent_bytes = 0
        start = time.time()

        def read_chunk(size_):
            return fh.read(size_)

        def progress(total, success, error):
            nonlocal sent_bytes
            # xmodem doesn't expose exact byte count; approximate by blocks
            # 128 or 1024 (+headers). We'll track file read position instead.
            sent_bytes = fh.tell()
            pct = min(100.0, (sent_bytes / max(1, size)) * 100.0)
            sys.stderr.write(f"\rSending {args.file}  {pct:5.1f}%  ({human(sent_bytes)}/{human(size)})")
            sys.stderr.flush()
            if args.debug and error:
                print(f"\nDEBUG: Transfer error - total: {total}, success: {success}, error: {error}", file=sys.stderr)

        # Wait for receiver to send initial NAK/C to start transmission
        print("Waiting for receiver to initiate transfer...", file=sys.stderr)
        
        # Much longer timeout for initial handshake
        initial_timeout = max(args.timeout * 15, 30.0)  # At least 30 seconds
        ser.timeout = initial_timeout
        
        # Increase retry count for problematic connections
        retry_count = max(args.retry, 30)
        
        ok = modem.send(
            stream=fh,
            retry=retry_count,
            timeout=args.timeout,
            quiet=False,
            callback=progress
        )
        dur = max(1e-6, time.time() - start)
        sys.stderr.write("\n")
        if not ok:
            print("Transfer failed (receiver did not acknowledge).", file=sys.stderr)
            print("Troubleshooting tips:", file=sys.stderr)
            print("  1. Try with --debug to see communication details", file=sys.stderr)
            print("  2. Verify receiver is in XMODEM receive mode", file=sys.stderr)
            print("  3. Try different baud rates: --baud 9600 or --baud 57600", file=sys.stderr)
            print("  4. Try checksum mode: --checksum", file=sys.stderr)
            print("  5. Try with hardware flow control: --rtscts", file=sys.stderr)
            sys.exit(2)
        print(f"Sent {human(sent_bytes)} in {dur:.2f}s  (~{human(sent_bytes/dur)}/s)")
    finally:
        if fh:
            try: 
                fh.close()
            except Exception: 
                pass
        ser.close()

def cmd_recv(args):
    ser = open_serial(args.port, args.baud, args.rtscts, args.dsrdtr, args.timeout)
    try:
        # Add CRC mode option and pass to modem
        crc_mode = getattr(args, 'crc', True)  # Default to CRC mode
        modem = make_modem(ser, args.x1k, args.debug, crc_mode)

        # Prepare output file (avoid overwrite unless --force)
        if os.path.exists(args.out) and not args.force:
            print(f"Refusing to overwrite existing file: {args.out} (use --force)", file=sys.stderr)
            sys.exit(3)

        tmp = args.out + ".part"
        fh = open(tmp, "wb")
        received = 0
        start = time.time()

        def write_chunk(data):
            nonlocal received
            fh.write(data)
            received += len(data)
            pct = f"{human(received)}"
            sys.stderr.write(f"\rReceiving -> {args.out}  {pct}")
            sys.stderr.flush()

        # Increase retry count for problematic connections
        retry_count = max(args.retry, 30)

        ok = modem.recv(
            stream=fh,
            retry=retry_count,
            timeout=args.timeout,
            quiet=False,
            callback=None  # write progress handled in write_chunk via the stream
        )
        fh.flush()
        fh.close()
        sys.stderr.write("\n")
        if not ok or received == 0:
            try: os.remove(tmp)
            except Exception: pass
            print("Receive failed (no data or not acknowledged).", file=sys.stderr)
            sys.exit(4)
        os.replace(tmp, args.out)
        dur = max(1e-6, time.time() - start)
        print(f"Received {human(received)} in {dur:.2f}s  (~{human(received/dur)}/s)")
    finally:
        ser.close()

def main():
    p = argparse.ArgumentParser(
        description="XMODEM/XMODEM-1k serial send/receive (macOS/Linux)."
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--port", "-p", required=True,
                        help="Serial device (e.g. /dev/tty.usbserial-XXX or /dev/ttyUSB0)")
    common.add_argument("--baud", "-b", type=int, default=115200, help="Baud rate (default: 115200)")
    common.add_argument("--timeout", type=float, default=3.0, help="Read/write timeout seconds (default: 3.0)")
    common.add_argument("--rtscts", action="store_true", help="Enable RTS/CTS hardware flow control")
    common.add_argument("--dsrdtr", action="store_true", help="Enable DSR/DTR hardware flow control")
    common.add_argument("--retry", type=int, default=16, help="Retry count per block (default: 16)")
    common.add_argument("--1k", dest="x1k", action="store_true", help="Use XMODEM-1k (1024B blocks)")
    common.add_argument("--debug", action="store_true", help="Enable debug output")
    common.add_argument("--checksum", dest="crc", action="store_false", 
                        help="Use checksum mode instead of CRC (less reliable but may work with older receivers)")

    sp_send = sub.add_parser("send", parents=[common], help="Send a file using XMODEM")
    sp_send.add_argument("file", help="Path to file to send")
    sp_send.set_defaults(func=cmd_send)

    sp_recv = sub.add_parser("recv", parents=[common], help="Receive a file using XMODEM")
    sp_recv.add_argument("--out", "-o", required=True, help="Output file path")
    sp_recv.add_argument("--force", "-f", action="store_true", help="Overwrite output if exists")
    sp_recv.set_defaults(func=cmd_recv)

    args = p.parse_args()
    try:
        args.func(args)
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        sys.exit(130)

if __name__ == "__main__":
    main()

