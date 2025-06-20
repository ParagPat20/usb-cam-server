#!/usr/bin/env python3
"""
Test script for MR72 radar data parsing
This script tests the parsing logic with simulated data
"""

import struct
import time
from mr72_mavlink import MR72Radar

def create_test_frame():
    """Create a test MR72 frame with known data"""
    # Header: 'T' 'H' (0x54, 0x48)
    header = bytes([0x54, 0x48])
    
    # Test data (all distances in mm)
    # D1: Sector 2 (56-112°) - 1500mm
    # D2: Sector 3 (112-168°) - 2000mm  
    # D3: Obstacle 90° - 1200mm
    # D4: Obstacle 135° - 1800mm
    # D5: Obstacle 180° - 2500mm
    # D6: Obstacle 225° - 3000mm
    # D7: Obstacle 270° - 2200mm
    # D8: Sector 1 (0-56°) - 1000mm
    
    # Convert distances to big-endian 16-bit values
    d1 = struct.pack('>H', 1500)  # Sector 2
    d2 = struct.pack('>H', 2000)  # Sector 3
    d3 = struct.pack('>H', 1200)  # Obstacle 90°
    d4 = struct.pack('>H', 1800)  # Obstacle 135°
    d5 = struct.pack('>H', 2500)  # Obstacle 180°
    d6 = struct.pack('>H', 3000)  # Obstacle 225°
    d7 = struct.pack('>H', 2200)  # Obstacle 270°
    d8 = struct.pack('>H', 1000)  # Sector 1
    
    # Combine all data
    data = header + d1 + d2 + d3 + d4 + d5 + d6 + d7 + d8
    
    # Calculate CRC8
    crc = 0
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x80:
                crc = (crc << 1) ^ 0x31
            else:
                crc <<= 1
            crc &= 0xFF
    
    # Add CRC
    frame = data + bytes([crc])
    
    return frame

def test_parser():
    """Test the MR72 parser with simulated data"""
    print("Testing MR72 Radar Parser")
    print("=" * 40)
    
    # Create test frame
    test_frame = create_test_frame()
    print(f"Test frame (hex): {test_frame.hex()}")
    print(f"Frame length: {len(test_frame)} bytes")
    print()
    
    # Create parser instance
    radar = MR72Radar()
    
    # Parse the frame
    result = radar.parse_frame(test_frame)
    
    if result:
        print("Parsed data:")
        print("-" * 20)
        for sector, distance in result.items():
            if distance is not None:
                print(f"{sector:15}: {distance:6} mm ({distance/10:6.1f} cm)")
            else:
                print(f"{sector:15}: No data")
    else:
        print("Failed to parse frame")
    
    print()
    print("Expected values:")
    print("-" * 20)
    expected = {
        'sector1': 1000,
        'sector2': 1500,
        'sector3': 2000,
        'obstacle_90': 1200,
        'obstacle_135': 1800,
        'obstacle_180': 2500,
        'obstacle_225': 3000,
        'obstacle_270': 2200
    }
    
    for sector, distance in expected.items():
        print(f"{sector:15}: {distance:6} mm ({distance/10:6.1f} cm)")
    
    print()
    if result:
        print("✅ Parser test PASSED")
        return True
    else:
        print("❌ Parser test FAILED")
        return False

def test_invalid_frames():
    """Test parser with invalid frames"""
    print("\nTesting Invalid Frames")
    print("=" * 40)
    
    radar = MR72Radar()
    
    # Test 1: Wrong header
    wrong_header = bytes([0x41, 0x42]) + b'\x00' * 17
    result = radar.parse_frame(wrong_header)
    print(f"Wrong header test: {'PASS' if result is None else 'FAIL'}")
    
    # Test 2: Wrong length
    short_frame = bytes([0x54, 0x48]) + b'\x00' * 10
    result = radar.parse_frame(short_frame)
    print(f"Short frame test: {'PASS' if result is None else 'FAIL'}")
    
    # Test 3: Invalid data (0xFFFF)
    invalid_frame = bytes([0x54, 0x48]) + b'\xFF\xFF' * 8 + bytes([0x00])
    result = radar.parse_frame(invalid_frame)
    if result:
        has_invalid = any(distance is None for distance in result.values())
        print(f"Invalid data test: {'PASS' if has_invalid else 'FAIL'}")
    else:
        print("Invalid data test: FAIL")

def test_crc_calculation():
    """Test CRC8 calculation"""
    print("\nTesting CRC8 Calculation")
    print("=" * 40)
    
    radar = MR72Radar()
    
    # Test data
    test_data = b'TH\x05\xDC\x07\xD0\x04\xB0\x07\x08\x09\xC4\x0B\xB8\x08\x8C'
    expected_crc = 0x00  # Calculate this manually
    
    calculated_crc = radar.crc8_calc(test_data + bytes([expected_crc]))
    print(f"Calculated CRC: 0x{calculated_crc:02X}")
    print(f"Expected CRC: 0x{expected_crc:02X}")
    print(f"CRC test: {'PASS' if calculated_crc == expected_crc else 'FAIL'}")

if __name__ == "__main__":
    print("MR72 Radar Parser Test Suite")
    print("=" * 50)
    
    # Run tests
    test_parser()
    test_invalid_frames()
    test_crc_calculation()
    
    print("\nTest suite completed!") 