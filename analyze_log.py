#!/usr/bin/env python3
"""
analyze_log.py – Quick-and-dirty flight-log analyser for ArduPilot *.BIN DataFlash logs.

The script extracts:
  • Distance covered (from GPS)
  • Altitude profile / max / min
  • Battery voltage, current, total consumption
  • Motor output PWM statistics
  • Overall efficiency (metres per mAh)

It prints a console summary and, if matplotlib is available, also saves plots to
`plots/` next to the log.

Usage:
    python analyze_log.py <path/to/log.BIN> [--plots]

Requires:
    pymavlink  (already in requirements.txt)
    numpy      (install if missing)
    matplotlib (optional – only for plots)

The parser is intentionally lenient – if certain messages (e.g. BAT or RCOU)
are not present in the log it will simply skip those analyses.
"""

import argparse
import os
import math
from collections import defaultdict
from datetime import timedelta
from typing import List, Tuple

import numpy as np
from pymavlink import mavutil

# -----------------------------------------------------------------------------
# Utility helpers
# -----------------------------------------------------------------------------

def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return distance in metres between two WGS-84 coords using the Haversine formula."""
    R = 6371000.0  # Earth radius (m)
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def maybe_import(name: str):
    """Return imported module (supports dotted paths) or None if import fails."""
    import importlib
    try:
        return importlib.import_module(name)
    except ImportError:
        return None


# -----------------------------------------------------------------------------
# Main log-processing routine
# -----------------------------------------------------------------------------

def process_log(path: str):
    mlog = mavutil.mavlink_connection(path, dialect="ardupilotmega", notimestamps=False)

    gps: List[Tuple[float, float, float, float]] = []  # time, lat, lon, alt (m)
    bats: List[Tuple[float, float, float]] = []        # time, voltage (V), current (A)
    rcout: List[Tuple[float, List[int]]] = []          # time, [pwm outputs]
    baro: List[Tuple[float, float]] = []              # time, altitude (m)
    attitudes: List[Tuple[float, float, float, float]] = []  # time, roll, pitch, yaw deg

    t_min = float('inf')
    t_max = 0.0

    while True:
        # blocking=True ensures we iterate until end-of-file, not just until a short pause
        msg = mlog.recv_match(blocking=True)
        if msg is None:
            break  # EOF reached

        # ------------------------------------------------------------------
        # Extract a monotonic timestamp (seconds since boot) from the message.
        # Only consider *on-board* time fields to avoid mixing with host wall-time.
        # ------------------------------------------------------------------
        t = None
        if hasattr(msg, 'TimeUS'):
            t = msg.TimeUS / 1e6  # μs → s
        elif hasattr(msg, 'time_boot_us'):
            t = msg.time_boot_us / 1e6
        elif hasattr(msg, 'TimeMS'):
            t = msg.TimeMS / 1e3   # ms → s
        elif hasattr(msg, 'time_boot_ms'):
            t = msg.time_boot_ms / 1e3
        # If none of the above exist, we skip – prevents mixing in wall-clock times
        if t is None:
            continue

        # Track global time bounds
        if t < t_min:
            t_min = t
        if t > t_max:
            t_max = t

        name = msg.get_type()

        # ---------------- GPS position ----------------
        if name in ("GPS", "GPS2") and hasattr(msg, 'Lat') and hasattr(msg, 'Lng'):
            raw_lat = msg.Lat
            raw_lon = msg.Lng
            # Latitude/longitude: determine scaling automatically
            if abs(raw_lat) > 180:
                lat = raw_lat / 1e7
                lon = raw_lon / 1e7
            else:
                lat = raw_lat
                lon = raw_lon

            # Altitude – detect if in cm (DataFlash) or already m
            if hasattr(msg, 'RelAlt') and not math.isnan(msg.RelAlt):
                alt_raw = msg.RelAlt
            else:
                alt_raw = getattr(msg, 'Alt', 0)

            if abs(alt_raw) > 1000:  # likely centimetres
                alt = alt_raw / 100.0
            else:
                alt = alt_raw
            gps.append((t, lat, lon, alt))

        # ---------------- Barometer ----------------
        if name == "BARO" and hasattr(msg, 'Alt'):
            baro_alt = float(msg.Alt)
            baro.append((t, baro_alt))

        # ---------------- Attitude ----------------
        if name in ("ATT", "ATTITUDE"):
            if name == "ATT":  # ArduPilot DataFlash
                roll = msg.Roll / 100.0  # cdeg -> deg
                pitch = msg.Pitch / 100.0
                yaw = msg.Yaw / 100.0
            else:
                roll = math.degrees(msg.roll)
                pitch = math.degrees(msg.pitch)
                yaw = math.degrees(msg.yaw)
            attitudes.append((t, roll, pitch, yaw))

        # ---------------- Battery ----------------
        if name in ("BAT", "CURR", "BATTERY_STATUS"):
            # Use whatever fields are available
            volt = None
            cur = None
            if hasattr(msg, 'Volt'):
                volt = float(msg.Volt)
            elif hasattr(msg, 'VoltStart'):  # some variants
                volt = float(msg.VoltStart)

            if hasattr(msg, 'Curr'):
                cur = float(msg.Curr)
            elif hasattr(msg, 'Current_battery'):
                cur = float(msg.Current_battery)

            # Heuristic unit correction: if values look too large, assume they were *100
            if volt is not None and volt > 70:
                volt /= 100.0
            if cur is not None and cur > 500:  # improbable >500 A
                cur /= 100.0

            if volt is not None or cur is not None:
                bats.append((t, volt or np.nan, cur or np.nan))

        # ---------------- Motor outputs ----------------
        if name in ("RCOU", "RCOUT", "SERVO_OUTPUT_RAW", "ACTUATOR_OUTPUT_STATUS"):
            ch_values = []
            # Gather numeric fields starting with 'C' followed by digits e.g. C1-C8
            for field in msg.get_fieldnames():
                if field.startswith('C') and field[1:].isdigit():
                    ch_values.append(getattr(msg, field))
            if ch_values:
                rcout.append((t, ch_values))

    # ---------------------------------------------------------------------
    # Post-processing & metrics
    # ---------------------------------------------------------------------

    summary = {}

    # --- Flight time ---
    if t_max > t_min and t_min != float('inf'):
        duration_s = t_max - t_min
        summary['flight_time'] = duration_s

    # --- Distance + Speed ---
    distance_m = 0.0
    speed_pts = []  # each: (time_mid, cum_dist_m, speed_mps)
    if len(gps) > 1:
        gps_sorted = sorted(gps, key=lambda x: x[0])
        cum = 0.0
        for (t1, lat1, lon1, _), (t2, lat2, lon2, _) in zip(gps_sorted[:-1], gps_sorted[1:]):
            d = haversine(lat1, lon1, lat2, lon2)
            dt = t2 - t1
            if dt > 0:
                cum += d
                sp = d / dt
                speed_pts.append(((t1 + t2)/2, cum, sp))
        distance_m = cum
        summary['distance_m'] = distance_m
        if speed_pts:
            speed_vals = [s for *_ , s in speed_pts]
            summary['speed_avg_mps'] = float(np.mean(speed_vals))
            summary['speed_max_mps'] = float(np.max(speed_vals))

    # --- Altitude (prefer barometer) ---
    if baro:
        alt_values = [a for _, a in baro]
    elif gps:
        alt_values = [a for *_, a in gps]
    else:
        alt_values = []

    if alt_values:
        summary['alt_min'] = float(np.min(alt_values))
        summary['alt_max'] = float(np.max(alt_values))
        summary['alt_mean'] = float(np.mean(alt_values))

    # --- Battery ---
    if bats:
        bats_sorted = sorted(bats, key=lambda x: x[0])
        volts = np.array([v for _, v, _ in bats_sorted if not math.isnan(v)])
        currs = np.array([c for _, _, c in bats_sorted if not math.isnan(c)])
        summary['bat_voltage_start'] = float(volts[0]) if volts.size else None
        summary['bat_voltage_end'] = float(volts[-1]) if volts.size else None
        summary['bat_voltage_avg'] = float(np.mean(volts)) if volts.size else None
        summary['bat_current_avg'] = float(np.mean(currs)) if currs.size else None

        # Energy consumption – integrate current over time → mAh
        consumed_mAh = 0.0
        for (t1, _, c1), (t2, _, c2) in zip(bats_sorted[:-1], bats_sorted[1:]):
            # linear interpolation between samples
            dt = t2 - t1
            if math.isnan(c1) or math.isnan(c2):
                continue
            consumed_mAh += (c1 + c2) / 2 * dt / 3600 * 1000  # A·s → mAh
        summary['bat_consumed_mAh'] = consumed_mAh

    # --- Efficiency ---
    if summary.get('distance_m') and summary.get('bat_consumed_mAh') and summary['bat_consumed_mAh'] > 0:
        distance_km = summary['distance_m'] / 1000.0
        consumed_Ah = summary['bat_consumed_mAh'] / 1000.0
        summary['efficiency_m_per_mAh'] = summary['distance_m'] / summary['bat_consumed_mAh']
        summary['efficiency_km_per_Ah'] = distance_km / consumed_Ah
        # If average voltage known, compute energy–based efficiency
        if summary.get('bat_voltage_avg'):
            energy_Wh = consumed_Ah * summary['bat_voltage_avg']
            if energy_Wh > 0:
                summary['efficiency_km_per_Wh'] = distance_km / energy_Wh
                summary['efficiency_Wh_per_km'] = energy_Wh / distance_km if distance_km > 0 else None

    # --- Motor outputs ---
    if rcout:
        # Flatten per-channel samples across time
        ch_dict = defaultdict(list)  # ch_idx -> samples
        for _, ch_values in rcout:
            for idx, val in enumerate(ch_values):
                ch_dict[idx].append(val)
        motor_stats = {}
        for idx, samples in ch_dict.items():
            if idx >= 6:  # Only channels 1-6
                continue
            motor_stats[idx + 1] = {
                'min': int(np.min(samples)),
                'max': int(np.max(samples)),
                'mean': float(np.mean(samples)),
            }
        summary['motor_stats'] = motor_stats

    # ------------------------------------------------------------
    # Attach interpolated current to each speed point for plotting
    # ------------------------------------------------------------
    if bats and speed_pts:
        bats_sorted = sorted(bats, key=lambda x: x[0])
        times_b = np.array([t for t, _, _ in bats_sorted])
        currents_b = np.array([c for _, _, c in bats_sorted])
        for i, (tmid, dist, sp) in enumerate(speed_pts):
            # np.interp needs ascending x, times_b is sorted
            cur = float(np.interp(tmid, times_b, currents_b))
            volts_b = np.array([v for _, v, _ in bats_sorted])
            volt = float(np.interp(tmid, times_b, volts_b))
            speed_pts[i] = (dist/1000.0, sp*3.6, cur, volt)  # km, km/h, A, V

    return summary, gps, baro, bats, rcout, speed_pts, attitudes


# -----------------------------------------------------------------------------
# Plotting (optional)
# -----------------------------------------------------------------------------

def save_plots(log_path: str, gps, baro, bats, rcout, speed_pts, attitudes):
    plt = maybe_import('matplotlib.pyplot')
    if plt is None:
        print("[WARN] matplotlib not available - skipping plots.")
        return

    base_name = os.path.splitext(os.path.basename(log_path))[0]
    out_dir = os.path.join(os.path.dirname(log_path), base_name)
    os.makedirs(out_dir, exist_ok=True)

    grid_kw = dict(linestyle='--', linewidth=0.4, color='gray', alpha=0.7)

    # --- GPS track ---
    if gps:
        lats = [lat for _, lat, _, _ in gps]
        lons = [lon for _, _, lon, _ in gps]
        plt.figure(figsize=(8, 8), dpi=200)
        plt.plot(lons, lats, linewidth=1.2)
        plt.title('GPS Track')
        plt.xlabel('Longitude')
        plt.ylabel('Latitude')
        plt.axis('equal')
        plt.grid(True, **grid_kw)
        plt.tight_layout()
        plt.savefig(os.path.join(out_dir, 'gps_track.png'), dpi=200)
        plt.close()

    # --- Altitude profile (prefer BARO) ---
    if baro:
        times = [t - baro[0][0] for t, _ in baro]
        alts = [alt for _, alt in baro]
    elif gps:
        times = [t - gps[0][0] for t, *_ in gps]
        alts = [alt for *_, alt in gps]
    else:
        times = alts = []

    if alts:
        plt.figure(figsize=(12, 4), dpi=200)
        plt.plot(times, alts, linewidth=1.2)
        plt.title('Altitude vs Time (Baro)')
        plt.xlabel('Time (s)')
        plt.ylabel('Altitude (m)')
        plt.grid(True, **grid_kw)
        plt.tight_layout()
        plt.savefig(os.path.join(out_dir, 'altitude.png'), dpi=200)
        plt.close()

    # --- Battery ---
    if bats:
        times = [t - bats[0][0] for t, *_ in bats]
        volts = [v for _, v, _ in bats]
        currs = [c for _, _, c in bats]

        fig, ax1 = plt.subplots(figsize=(12, 4), dpi=200)
        ax1.set_title('Battery Voltage / Current')
        ax1.plot(times, volts, color='tab:red', label='Voltage (V)')
        ax1.set_xlabel('Time (s)')
        ax1.set_ylabel('Voltage (V)', color='tab:red')
        ax1.tick_params(axis='y', labelcolor='tab:red')

        ax2 = ax1.twinx()
        ax2.plot(times, currs, color='tab:blue', label='Current (A)')
        ax2.set_ylabel('Current (A)', color='tab:blue')
        ax2.tick_params(axis='y', labelcolor='tab:blue')

        ax1.grid(True, **grid_kw)
        fig.tight_layout()
        fig.savefig(os.path.join(out_dir, 'battery.png'), dpi=200)
        plt.close(fig)

    # --- Motor outputs ---
    if rcout:
        times = [t - rcout[0][0] for t, _ in rcout]
        ch_count = max(len(vals) for _, vals in rcout)
        for ch in range(min(ch_count, 6)):
            samples = [vals[ch] if ch < len(vals) else np.nan for _, vals in rcout]
            plt.plot(times, samples, label=f'C{ch + 1}')
        plt.title('Motor Outputs (PWM)')
        plt.xlabel('Time (s)')
        plt.ylabel('PWM')
        plt.legend(ncol=3)
        plt.grid(True, **grid_kw)
        plt.tight_layout()
        plt.savefig(os.path.join(out_dir, 'motor_outputs.png'), dpi=200)
        plt.close()

    # --- Speed & Current vs Distance ---
    if speed_pts:
        if len(speed_pts[0]) == 4:
            dists = [d for d, *_ in speed_pts]
            speed_kmh = [v for _, v, _, _ in speed_pts]
            currents = [c for _, _, c, _ in speed_pts]
            volts = [vt for _, _, _, vt in speed_pts]
        else:
            # fallback (shouldn't occur)
            dists = [d for d, *_ in speed_pts]
            speed_kmh = currents = volts = []

        fig, ax1 = plt.subplots(figsize=(12,4), dpi=200)
        ax1.plot(dists, speed_kmh, color='tab:green', linewidth=1.2, label='Speed (km/h)')
        ax1.set_xlabel('Distance Covered (km)')
        ax1.set_ylabel('Speed (km/h)', color='tab:green')
        ax1.tick_params(axis='y', labelcolor='tab:green')
        ax1.grid(True, **grid_kw)

        ax2 = ax1.twinx()
        ax2.plot(dists, currents, color='tab:orange', linewidth=1.2, label='Current (A)')
        ax2.set_ylabel('Current (A)', color='tab:orange')
        ax2.tick_params(axis='y', labelcolor='tab:orange')

        # Third axis for voltage
        ax3 = ax1.twinx()
        ax3.spines["right"].set_position(("outward", 60))
        ax3.plot(dists, volts, color='tab:red', linewidth=1.2, label='Voltage (V)')
        ax3.set_ylabel('Voltage (V)', color='tab:red')
        ax3.tick_params(axis='y', labelcolor='tab:red')

        fig.tight_layout()
        fig.savefig(os.path.join(out_dir, 'speed_current_voltage_distance.png'), dpi=200)
        plt.close(fig)

    print(f"[OK] Plots saved to {out_dir}")

    # ------------- Interactive 3-D track with orientation -------------
    plotly = maybe_import('plotly.graph_objects')
    if plotly and gps:
        go = plotly
        # Local ENU conversion (simple equirect approx)
        lat0, lon0 = gps[0][1], gps[0][2]
        xs, ys, zs = [], [], []
        for _, lat, lon, alt in gps:
            dx = haversine(lat0, lon0, lat, lon0) * (1 if lon >= lon0 else -1)
            dy = haversine(lat0, lon0, lat0, lon)
            if lat < lat0:
                dy *= -1
            xs.append(dx)
            ys.append(dy)
            zs.append(alt)

        fig = go.Figure()
        fig.add_trace(go.Scatter3d(x=xs, y=ys, z=zs, mode='lines', line=dict(color='blue', width=4), name='Path'))

        # Add attitude cones every ~100th sample to keep light
        if attitudes:
            step = max(1, len(attitudes)//100)
            ux, uy, uz = [], [], []
            cone_x, cone_y, cone_z = [], [], []
            for i in range(0, len(attitudes), step):
                t, roll, pitch, yaw = attitudes[i]
                # find nearest gps sample index via simple search
                idx = min(range(len(gps)), key=lambda j: abs(gps[j][0]-t))
                cone_x.append(xs[idx]); cone_y.append(ys[idx]); cone_z.append(zs[idx])
                # orientation vector ~1m length in ENU frame from yaw
                rad = math.radians(yaw)
                ux.append(math.sin(rad))
                uy.append(math.cos(rad))
                uz.append(math.sin(math.radians(pitch)))
            fig.add_trace(go.Cone(x=cone_x, y=cone_y, z=cone_z, u=ux, v=uy, w=uz,
                                   sizemode='absolute', sizeref=2, colorscale='Viridis', showscale=False, name='Orientation'))

        fig.update_layout(scene=dict(xaxis_title='East (m)', yaxis_title='North (m)', zaxis_title='Alt (m)'),
                          title='3-D Flight Track with Orientation')
        html_path = os.path.join(out_dir, 'track_3d.html')
        fig.write_html(html_path)
        print(f"[OK] Interactive 3D map saved to {html_path}")


# -----------------------------------------------------------------------------
# CLI
# -----------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Analyze ArduPilot DataFlash *.BIN logs")
    parser.add_argument('log', help="Path to .BIN log file")
    parser.add_argument('--plots', action='store_true', help="Generate PNG plots (requires matplotlib)")
    args = parser.parse_args()

    if not os.path.isfile(args.log):
        raise FileNotFoundError(args.log)

    print(f"[INFO] Processing {args.log} …")
    summary, gps, baro, bats, rcout, speed_pts, attitudes = process_log(args.log)

    # ---------------- Print summary ----------------
    print("\n=== Flight Summary ===")
    if 'flight_time' in summary:
        print(f"Flight time        : {timedelta(seconds=summary['flight_time'])} (h:m:s)")
    if 'distance_m' in summary:
        print(f"Distance covered   : {summary['distance_m'] / 1000:.2f} km")
    if 'alt_min' in summary:
        print(f"Altitude (min/avg/max): {summary['alt_min']:.1f} / {summary['alt_mean']:.1f} / {summary['alt_max']:.1f} m")
    if 'speed_avg_mps' in summary:
        print(
            f"Ground speed        : {summary['speed_avg_mps']*3.6:.1f} km/h avg  |  {summary['speed_max_mps']*3.6:.1f} km/h max")
    if 'bat_voltage_start' in summary:
        print(f"Battery voltage    : {summary['bat_voltage_start']:.2f} → {summary['bat_voltage_end']:.2f} V (avg {summary['bat_voltage_avg']:.2f} V)")
    if 'bat_consumed_mAh' in summary:
        print(f"Battery consumed   : {summary['bat_consumed_mAh']:.0f} mAh")
    if 'efficiency_m_per_mAh' in summary:
        print(f"Efficiency (distance/charge): {summary['efficiency_m_per_mAh']:.1f} m per mAh | {summary['efficiency_km_per_Ah']:.2f} km per Ah")
    if 'efficiency_km_per_Wh' in summary:
        print(f"Energy efficiency            : {summary['efficiency_km_per_Wh']:.3f} km per Wh ({summary['efficiency_Wh_per_km']:.2f} Wh per km)")
    if 'motor_stats' in summary:
        print("Motor outputs (PWM):")
        for ch, stats in sorted(summary['motor_stats'].items()):
            if ch > 6:
                continue
            print(f"  C{ch}: {stats['min']}-{stats['max']} (avg {stats['mean']:.0f})")

    # ---------------- Plots ----------------
    if args.plots:
        save_plots(args.log, gps, baro, bats, rcout, speed_pts, attitudes)


if __name__ == "__main__":
    main() 