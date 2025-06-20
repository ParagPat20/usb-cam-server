#!/usr/bin/env python3
"""
MR72 Radar Monitor
Simple monitoring script to verify radar data and MAVLink communication
"""

import time
import socket
import struct
import threading
from mr72_mavlink import MR72Radar, MAVLinkSender

class MR72Monitor:
    def __init__(self, radar_port="/dev/ttyS0", mavlink_host="127.0.0.1", mavlink_port=14551):
        self.radar = MR72Radar(radar_port)
        self.mavlink = MAVLinkSender(mavlink_host, mavlink_port)
        self.running = False
        self.stats = {
            'frames_received': 0,
            'frames_parsed': 0,
            'mavlink_messages_sent': 0,
            'last_frame_time': None,
            'errors': 0
        }
        self.stats_lock = threading.Lock()
    
    def start(self):
        """Start monitoring"""
        print("Starting MR72 Radar Monitor")
        print("=" * 50)
        
        # Start radar
        if not self.radar.start():
            print("❌ Failed to start radar")
            return False
        
        # Connect to MAVLink
        if not self.mavlink.connect():
            print("❌ Failed to connect to MAVProxy")
            return False
        
        self.running = True
        
        # Start monitoring thread
        self.monitor_thread = threading.Thread(target=self.monitor_loop, daemon=True)
        self.monitor_thread.start()
        
        # Start stats display thread
        self.stats_thread = threading.Thread(target=self.display_stats, daemon=True)
        self.stats_thread.start()
        
        print("✅ Monitor started successfully")
        print("Press Ctrl+C to stop")
        return True
    
    def stop(self):
        """Stop monitoring"""
        self.running = False
        self.radar.stop()
        self.mavlink.disconnect()
        print("\n🛑 Monitor stopped")
    
    def monitor_loop(self):
        """Main monitoring loop"""
        while self.running:
            try:
                # Get latest radar data
                radar_data = self.radar.get_latest_data()
                
                with self.stats_lock:
                    self.stats['frames_received'] += 1
                    self.stats['last_frame_time'] = time.time()
                
                if radar_data:
                    with self.stats_lock:
                        self.stats['frames_parsed'] += 1
                    
                    # Display radar data
                    self.display_radar_data(radar_data)
                    
                    # Send MAVLink messages
                    self.send_mavlink_data(radar_data)
                    
                    with self.stats_lock:
                        self.stats['mavlink_messages_sent'] += 1
                
                time.sleep(0.1)  # 10 Hz update rate
                
            except Exception as e:
                with self.stats_lock:
                    self.stats['errors'] += 1
                print(f"❌ Error in monitor loop: {e}")
                time.sleep(1)
    
    def display_radar_data(self, data):
        """Display formatted radar data"""
        print("\n" + "="*60)
        print("MR72 RADAR DATA")
        print("="*60)
        
        # Display sectors
        print("SECTORS:")
        print("-" * 30)
        for sector in ['sector1', 'sector2', 'sector3']:
            if sector in data and data[sector] is not None:
                distance_cm = data[sector] / 10
                print(f"{sector:12}: {data[sector]:6} mm ({distance_cm:6.1f} cm)")
            else:
                print(f"{sector:12}: No data")
        
        # Display obstacles
        print("\nOBSTACLES:")
        print("-" * 30)
        obstacles = {
            'obstacle_90': '90°',
            'obstacle_135': '135°',
            'obstacle_180': '180°',
            'obstacle_225': '225°',
            'obstacle_270': '270°'
        }
        
        for obstacle, angle in obstacles.items():
            if obstacle in data and data[obstacle] is not None:
                distance_cm = data[obstacle] / 10
                print(f"{angle:6}: {data[obstacle]:6} mm ({distance_cm:6.1f} cm)")
            else:
                print(f"{angle:6}: No data")
        
        print("="*60)
    
    def send_mavlink_data(self, data):
        """Send radar data via MAVLink"""
        try:
            # Send sector data as distance sensors
            sector_orientations = {
                'sector1': 0,    # Forward
                'sector2': 45,   # 45 degrees right
                'sector3': -45   # 45 degrees left
            }
            
            for sector, orientation in sector_orientations.items():
                if sector in data and data[sector] is not None:
                    distance_cm = int(data[sector] / 10)
                    self.mavlink.send_distance_sensor(distance_cm, 0, orientation)
            
            # Create obstacle distance array
            obstacle_distances = [65535] * 72
            
            sector_mappings = {
                'sector1': (0, 56),
                'sector2': (56, 112),
                'sector3': (112, 168),
            }
            
            for sector, (start_angle, end_angle) in sector_mappings.items():
                if sector in data and data[sector] is not None:
                    distance_cm = int(data[sector] / 10)
                    start_idx = int(start_angle / 5)
                    end_idx = int(end_angle / 5)
                    for i in range(start_idx, min(end_idx, 72)):
                        obstacle_distances[i] = distance_cm
            
            self.mavlink.send_obstacle_distance(obstacle_distances)
            
        except Exception as e:
            print(f"❌ Error sending MAVLink data: {e}")
    
    def display_stats(self):
        """Display statistics every 5 seconds"""
        while self.running:
            time.sleep(5)
            
            with self.stats_lock:
                stats = self.stats.copy()
            
            print("\n" + "="*50)
            print("SYSTEM STATISTICS")
            print("="*50)
            print(f"Frames received: {stats['frames_received']}")
            print(f"Frames parsed: {stats['frames_parsed']}")
            print(f"MAVLink messages sent: {stats['mavlink_messages_sent']}")
            print(f"Errors: {stats['errors']}")
            
            if stats['last_frame_time']:
                time_since_last = time.time() - stats['last_frame_time']
                print(f"Time since last frame: {time_since_last:.1f}s")
            
            # Calculate success rate
            if stats['frames_received'] > 0:
                success_rate = (stats['frames_parsed'] / stats['frames_received']) * 100
                print(f"Success rate: {success_rate:.1f}%")
            
            print("="*50)

def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description="MR72 Radar Monitor")
    parser.add_argument("--radar-port", default="/dev/ttyS0", help="MR72 radar serial port")
    parser.add_argument("--mavlink-host", default="127.0.0.1", help="MAVProxy UDP host")
    parser.add_argument("--mavlink-port", type=int, default=14551, help="MAVProxy UDP port")
    parser.add_argument("--no-mavlink", action="store_true", help="Disable MAVLink output")
    
    args = parser.parse_args()
    
    print("MR72 Radar Monitor")
    print("=" * 50)
    print(f"Radar port: {args.radar_port}")
    print(f"MAVLink: {args.mavlink_host}:{args.mavlink_port}")
    print(f"MAVLink enabled: {not args.no_mavlink}")
    print()
    
    # Create monitor
    monitor = MR72Monitor(args.radar_port, args.mavlink_host, args.mavlink_port)
    
    try:
        if monitor.start():
            # Keep main thread alive
            while True:
                time.sleep(1)
        else:
            print("❌ Failed to start monitor")
    except KeyboardInterrupt:
        print("\n🛑 Shutting down...")
    finally:
        monitor.stop()

if __name__ == "__main__":
    main() 