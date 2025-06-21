#!/usr/bin/env python3
"""
Test script for MR72 radar protocol parsing
"""

import sys
import os

# Add current directory to path to import mr72_mavlink
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from mr72_mavlink import MR72Radar

def test_mr72_parsing():
    """Test MR72 frame parsing with sample data"""
    
    # Create radar instance
    radar = MR72Radar()
    
    # Sample MR72 frame data (19 bytes)
    # Header: TH (0x54, 0x48)
    # D1: Sector 2 (90 degrees) = 1000mm
    # D2: Sector 3 (180 degrees) = 2000mm  
    # D3: 90 degree sector = 1500mm
    # D4: 135 degree sector = 2500mm
    # D5: 180 degree sector = 3000mm
    # D6: 225 degree sector = 3500mm
    # D7: 270 degree sector = 4000mm
    # D8: Sector 1 (0 degrees) = 500mm
    # CRC8: 0x00 (dummy)
    
    sample_frame = bytes([
        0x54, 0x48,  # Header: TH
        0x03, 0xE8,  # D1: Sector 2 = 1000mm (0x03E8)
        0x07, 0xD0,  # D2: Sector 3 = 2000mm (0x07D0)
        0x05, 0xDC,  # D3: 90 degree = 1500mm (0x05DC)
        0x09, 0xC4,  # D4: 135 degree = 2500mm (0x09C4)
        0x0B, 0xB8,  # D5: 180 degree = 3000mm (0x0BB8)
        0x0D, 0xAC,  # D6: 225 degree = 3500mm (0x0DAC)
        0x0F, 0xA0,  # D7: 270 degree = 4000mm (0x0FA0)
        0x01, 0xF4,  # D8: Sector 1 = 500mm (0x01F4)
        0x00          # CRC8 (dummy)
    ])
    
    print("Testing MR72 frame parsing...")
    print(f"Sample frame: {sample_frame.hex()}")
    
    # Parse the frame
    result = radar.parse_mr72_frame(sample_frame)
    
    if result:
        print("\nParsed data:")
        print(f"Sector 1 (0°): {result['sector1']} mm")
        print(f"Sector 2 (90°): {result['sector2']} mm")
        print(f"Sector 3 (180°): {result['sector3']} mm")
        print(f"90° sector: {result['sector_90']} mm")
        print(f"135° sector: {result['sector_135']} mm")
        print(f"180° sector: {result['sector_180']} mm")
        print(f"225° sector: {result['sector_225']} mm")
        print(f"270° sector: {result['sector_270']} mm")
        
        # Test invalid distance handling
        print("\nTesting invalid distance handling...")
        invalid_frame = bytes([
            0x54, 0x48,  # Header: TH
            0xFF, 0xFF,  # D1: Invalid (0xFFFF)
            0x07, 0xD0,  # D2: Valid = 2000mm
            0xFF, 0xFF,  # D3: Invalid (0xFFFF)
            0x09, 0xC4,  # D4: Valid = 2500mm
            0xFF, 0xFF,  # D5: Invalid (0xFFFF)
            0x0D, 0xAC,  # D6: Valid = 3500mm
            0xFF, 0xFF,  # D7: Invalid (0xFFFF)
            0x01, 0xF4,  # D8: Valid = 500mm
            0x00          # CRC8 (dummy)
        ])
        
        invalid_result = radar.parse_mr72_frame(invalid_frame)
        if invalid_result:
            print("\nParsed data with invalid distances:")
            for key, value in invalid_result.items():
                if value is None:
                    print(f"{key}: Invalid/None")
                else:
                    print(f"{key}: {value} mm")
        
        print("\n✓ MR72 parsing test passed!")
        return True
    else:
        print("✗ MR72 parsing test failed!")
        return False

def test_invalid_frames():
    """Test handling of invalid frames"""
    
    radar = MR72Radar()
    
    print("\nTesting invalid frame handling...")
    
    # Test wrong header
    wrong_header = bytes([0x41, 0x42]) + b'\x00' * 17
    result = radar.parse_mr72_frame(wrong_header)
    if result is None:
        print("✓ Wrong header correctly rejected")
    else:
        print("✗ Wrong header not rejected")
        return False
    
    # Test wrong length
    wrong_length = bytes([0x54, 0x48]) + b'\x00' * 10  # Too short
    result = radar.parse_mr72_frame(wrong_length)
    if result is None:
        print("✓ Wrong length correctly rejected")
    else:
        print("✗ Wrong length not rejected")
        return False
    
    print("✓ Invalid frame handling test passed!")
    return True

if __name__ == "__main__":
    print("MR72 Radar Protocol Parser Test")
    print("=" * 40)
    
    success = True
    success &= test_mr72_parsing()
    success &= test_invalid_frames()
    
    if success:
        print("\n🎉 All tests passed!")
        print("\nThe MR72 radar bridge is ready to use.")
        print("Run: python3 mr72_mavlink.py --help")
    else:
        print("\n❌ Some tests failed!")
        sys.exit(1) 