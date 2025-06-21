from pymavlink import mavutil

# Use the persistent path for your FC:
fc_id = '/dev/serial/by-id/usb-ArduPilot_Pixhawk6X_36004E001351333031333637-if00'

master = mavutil.mavlink_connection(
    fc_id,
    baud=115200,
    source_system=1,
    source_component=158
)
print("Waiting for heartbeat from FC on:", fc_id)
master.wait_heartbeat()
print("🎉 Connected to FC:", master.target_system, master.target_component)
