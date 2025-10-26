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

def make_modem(ser, use_1k: bool, debug=False):
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
        # Give the receiver time to process the data
        time.sleep(0.001)  # 1ms delay
        return written

    return (XMODEM1k if use_1k else XMODEM)(getc, putc)

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
        modem = make_modem(ser, args.x1k, args.debug)

        # Clear buffers and wait for receiver to be ready
        ser.reset_input_buffer()
        ser.reset_output_buffer()
        time.sleep(0.5)  # Give receiver time to initialize
        
        # Drain any stale data
        while ser.in_waiting > 0:
            stale_data = ser.read(ser.in_waiting)
            if args.debug:
                print(f"DEBUG: Drained {len(stale_data)} stale bytes: {stale_data.hex()}", file=sys.stderr)
            time.sleep(0.1)

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

        # Wait for receiver to send initial NAK/C to start transmission
        print("Waiting for receiver to initiate transfer...", file=sys.stderr)
        initial_timeout = args.timeout * 10  # Give more time for initial handshake
        ser.timeout = initial_timeout
        
        ok = modem.send(
            stream=fh,
            retry=args.retry,
            timeout=args.timeout,
            quiet=False,
            callback=progress
        )
        dur = max(1e-6, time.time() - start)
        sys.stderr.write("\n")
        if not ok:
            print("Transfer failed (receiver did not acknowledge).", file=sys.stderr)
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
        modem = make_modem(ser, args.x1k, args.debug)

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

        ok = modem.recv(
            stream=fh,
            retry=args.retry,
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

