# XMODEM File Transfer Utility

A robust Python-based XMODEM/XMODEM-1k file transfer utility for serial communication on macOS and Linux systems. This tool provides reliable file transfers over serial connections with comprehensive error handling and debugging capabilities.

## Features

- **XMODEM and XMODEM-1k Protocol Support**: Standard 128-byte and extended 1024-byte block transfers
- **Bidirectional Transfer**: Send and receive files via serial connection
- **Real-time Progress**: Live transfer progress with speed monitoring
- **Robust Error Handling**: Comprehensive retry mechanisms and error recovery
- **Debug Mode**: Detailed communication logging for troubleshooting
- **Hardware Flow Control**: Support for RTS/CTS and DSR/DTR flow control
- **Safe File Operations**: Prevents accidental overwrites with confirmation prompts

## Installation

### Prerequisites

- Python 3.6 or higher
- Serial port access (USB-to-serial adapter, built-in serial port, etc.)

### Setup

1. **Clone or download the repository**:
   ```bash
   git clone <repository-url>
   cd xmodem-fs
   ```

2. **Create a virtual environment** (recommended):
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On macOS/Linux
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Make scripts executable**:
   ```bash
   chmod +x main.py serial_test.py
   ```

## Usage

### Basic Commands

The utility supports two main operations: `send` and `recv`.

#### Sending Files

```bash
./main.py send <file> --port <serial_port> [options]
```

**Example**:
```bash
./main.py send firmware.bin --port /dev/tty.usbserial-A50285BI
```

#### Receiving Files

```bash
./main.py recv --out <output_file> --port <serial_port> [options]
```

**Example**:
```bash
./main.py recv --out received_data.bin --port /dev/tty.usbserial-A50285BI
```

### Command Line Options

#### Common Options (available for both send and recv)

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--port` | `-p` | Required | Serial device path (e.g., `/dev/tty.usbserial-XXX`) |
| `--baud` | `-b` | `115200` | Baud rate for serial communication |
| `--timeout` | | `3.0` | Read/write timeout in seconds |
| `--retry` | | `16` | Number of retries per block |
| `--1k` | | `false` | Use XMODEM-1k (1024-byte blocks) instead of standard XMODEM |
| `--rtscts` | | `false` | Enable RTS/CTS hardware flow control |
| `--dsrdtr` | | `false` | Enable DSR/DTR hardware flow control |
| `--debug` | | `false` | Enable detailed debug output |

#### Send-specific Options

| Option | Description |
|--------|-------------|
| `file` | Path to the file to send (positional argument) |

#### Receive-specific Options

| Option | Short | Description |
|--------|-------|-------------|
| `--out` | `-o` | Output file path (required) |
| `--force` | `-f` | Overwrite existing output file without confirmation |

### Examples

#### Basic File Transfer

```bash
# Send a firmware file
./main.py send firmware.hex --port /dev/tty.usbserial-A50285BI

# Receive a data dump
./main.py recv --out data_dump.bin --port /dev/tty.usbserial-A50285BI
```

#### High-Speed Transfer with XMODEM-1k

```bash
# Send using 1024-byte blocks for faster transfer
./main.py send large_file.bin --port /dev/tty.usbserial-A50285BI --1k

# Receive with custom baud rate
./main.py recv --out output.bin --port /dev/tty.usbserial-A50285BI --baud 230400 --1k
```

#### Troubleshooting with Debug Mode

```bash
# Enable debug output to see detailed communication
./main.py send test.bin --port /dev/tty.usbserial-A50285BI --debug --timeout 5.0
```

#### Hardware Flow Control

```bash
# Enable RTS/CTS flow control for devices that require it
./main.py send data.bin --port /dev/tty.usbserial-A50285BI --rtscts
```

## Finding Serial Ports

### macOS
```bash
# List all serial devices
ls /dev/tty.*

# Common patterns:
# USB-Serial adapters: /dev/tty.usbserial-*
# USB-Modem devices: /dev/tty.usbmodem*
# Built-in serial: /dev/tty.Bluetooth-Incoming-Port
```

### Linux
```bash
# List all serial devices
ls /dev/tty*

# Common patterns:
# USB devices: /dev/ttyUSB*
# ACM devices: /dev/ttyACM*
# Built-in serial: /dev/ttyS*
```

## Troubleshooting

### Common Issues and Solutions

#### 1. "expected ACK; got None" Error

This indicates no response from the receiver. Try:

```bash
# Test basic serial communication first
./serial_test.py --port /dev/tty.your-device

# Increase timeout and enable debug
./main.py send file.bin --port /dev/tty.your-device --timeout 10.0 --debug
```

#### 2. "expected ACK; got NAK" Error

The receiver is rejecting blocks. Solutions:

```bash
# Try different baud rates
./main.py send file.bin --port /dev/tty.your-device --baud 9600

# Enable hardware flow control if supported
./main.py send file.bin --port /dev/tty.your-device --rtscts

# Use standard XMODEM instead of 1k
./main.py send file.bin --port /dev/tty.your-device  # (remove --1k)
```

#### 3. Permission Denied

```bash
# Add user to dialout group (Linux)
sudo usermod -a -G dialout $USER

# Or run with sudo (temporary solution)
sudo ./main.py send file.bin --port /dev/ttyUSB0
```

#### 4. Port Already in Use

```bash
# Check what's using the port
lsof /dev/tty.your-device

# Kill other processes or use a different terminal
```

### Serial Communication Testing

Use the included test utility to diagnose connection issues:

```bash
# Test basic connectivity
./serial_test.py --port /dev/tty.usbserial-A50285BI

# Monitor port activity
./serial_test.py --port /dev/tty.usbserial-A50285BI --monitor
```

## Protocol Details

### XMODEM Protocol

- **Block Size**: 128 bytes (standard) or 1024 bytes (XMODEM-1k)
- **Error Detection**: Checksum (standard) or CRC (XMODEM-CRC)
- **Flow Control**: Software-based with ACK/NAK responses
- **Timeout Handling**: Configurable timeouts with retry mechanisms

### Transfer Process

1. **Handshake**: Receiver sends NAK (0x15) or 'C' (0x43) to initiate
2. **Data Transfer**: Sender transmits blocks with sequence numbers
3. **Acknowledgment**: Receiver responds with ACK (0x06) or NAK (0x15)
4. **Completion**: Sender transmits EOT (0x04) to signal end

## Performance Tips

1. **Use XMODEM-1k** for faster transfers: `--1k`
2. **Increase baud rate** if supported: `--baud 230400`
3. **Enable hardware flow control** for reliable high-speed transfers: `--rtscts`
4. **Adjust timeout** for slow or unreliable connections: `--timeout 10.0`

## Dependencies

- **pyserial** (3.5): Cross-platform serial port access
- **xmodem** (0.4.7): XMODEM protocol implementation

## License

This project is open source. Please check the license file for details.

## Contributing

Contributions are welcome! Please feel free to submit issues, feature requests, or pull requests.

## Support

For issues and questions:
1. Check the troubleshooting section above
2. Run with `--debug` flag to get detailed output
3. Use `serial_test.py` to verify basic connectivity
4. Submit an issue with debug output and system details