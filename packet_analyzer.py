#!/usr/bin/env python3
"""
XMODEM packet analyzer - helps debug packet format issues
"""

import sys
import binascii

def analyze_xmodem_packet(packet_hex):
    """Analyze an XMODEM packet and show its structure"""
    try:
        packet = bytes.fromhex(packet_hex.replace(' ', ''))
    except ValueError:
        print("Invalid hex string")
        return
    
    if len(packet) < 4:
        print("Packet too short")
        return
    
    print(f"Packet length: {len(packet)} bytes")
    print(f"Raw packet: {packet.hex()}")
    print()
    
    # Parse header
    soh = packet[0]
    block_num = packet[1]
    block_inv = packet[2]
    
    print(f"SOH (Start of Header): 0x{soh:02x} ({'OK' if soh == 0x01 else 'ERROR - should be 0x01'})")
    print(f"Block number: {block_num}")
    print(f"Block number inverted: 0x{block_inv:02x} (should be 0x{(255 - block_num):02x})")
    
    if block_inv != (255 - block_num):
        print("ERROR: Block number inversion mismatch!")
    else:
        print("Block number inversion: OK")
    
    # Data portion
    if len(packet) >= 131:  # Minimum for data
        data = packet[3:131]
        print(f"Data ({len(data)} bytes): {data[:16].hex()}{'...' if len(data) > 16 else ''}")
        
        # Checksum analysis
        if len(packet) == 132:  # CRC mode
            crc_bytes = packet[131:133]
            crc = (crc_bytes[0] << 8) | crc_bytes[1]
            print(f"CRC: 0x{crc:04x} ({crc_bytes.hex()})")
            
            # Calculate expected CRC
            expected_crc = calculate_crc16(data)
            print(f"Expected CRC: 0x{expected_crc:04x}")
            if crc == expected_crc:
                print("CRC: OK")
            else:
                print("CRC: MISMATCH!")
                
        elif len(packet) == 133:  # Checksum mode  
            checksum = packet[131]
            print(f"Checksum: 0x{checksum:02x}")
            
            # Calculate expected checksum
            expected_checksum = sum(data) & 0xff
            print(f"Expected checksum: 0x{expected_checksum:02x}")
            if checksum == expected_checksum:
                print("Checksum: OK")
            else:
                print("Checksum: MISMATCH!")
        else:
            print(f"Unknown packet format - unexpected length: {len(packet)}")

def calculate_crc16(data):
    """Calculate CRC-16 (XMODEM variant)"""
    crc = 0
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = (crc << 1) ^ 0x1021
            else:
                crc <<= 1
            crc &= 0xffff
    return crc

def main():
    if len(sys.argv) != 2:
        print("Usage: python3 packet_analyzer.py <hex_packet>")
        print("Example: python3 packet_analyzer.py '0101fe44bf3fb3db4f11...'")
        sys.exit(1)
    
    analyze_xmodem_packet(sys.argv[1])

if __name__ == "__main__":
    main()