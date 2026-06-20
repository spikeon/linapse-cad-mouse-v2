import sys
import time
import subprocess
import struct
import math
from . import state

def fft(x):
    N = len(x)
    if N <= 1:
        return x
    even = fft(x[0::2])
    odd = fft(x[1::2])
    
    T = []
    for k in range(N // 2):
        angle = -2.0 * math.pi * k / N
        c = math.cos(angle)
        s = math.sin(angle)
        ok_r, ok_i = odd[k]
        t_r = ok_r * c - ok_i * s
        t_i = ok_r * s + ok_i * c
        T.append((t_r, t_i))
    
    res = [None] * N
    for k in range(N // 2):
        ev_r, ev_i = even[k]
        t_r, t_i = T[k]
        res[k] = (ev_r + t_r, ev_i + t_i)
        res[k + N // 2] = (ev_r - t_r, ev_i - t_i)
    return res

bands_bins = [
    (1, 1),      # Band 0: ~86Hz
    (2, 2),      # Band 1: ~172Hz
    (3, 4),      # Band 2: ~258Hz - ~344Hz
    (5, 8),      # Band 3: ~430Hz - ~689Hz
    (9, 15),     # Band 4: ~775Hz - ~1292Hz
    (16, 26),    # Band 5: ~1378Hz - ~2239Hz
    (27, 46),    # Band 6: ~2325Hz - ~3962Hz
    (47, 120)    # Band 7: ~4048Hz - ~10336Hz
]

bands_scales = [
    1.0 / 50.0,
    1.0 / 25.0,
    1.0 / 10.0,
    1.0 / 5.0,
    1.0 / 3.0,
    1.0 / 2.0,
    1.0 / 1.2,
    1.0 / 0.6
]

def equalizer_watcher(actions_ref):
    # Only run audio capture on Linux
    if sys.platform in ("win32", "darwin"):
        phase = 0.0
        while True:
            try:
                active = False
                actions = actions_ref[0]
                if actions and "modes" in actions:
                    current_mode = actions.get("current_mode", "Default")
                    if current_mode in actions["modes"]:
                        led_config = actions["modes"][current_mode].get("led", {})
                        if led_config.get("effect") == "equalizer":
                            active = True
                
                if active and not state.flashing_active:
                    phase += 0.05
                    temp = [0] * 8
                    for i in range(8):
                        temp[i] = int(50 + 50 * math.sin(phase + i * 0.5))
                    eq_str = " ".join(map(str, temp))
                    eq_ws_str = ":".join(map(str, temp))
                    
                    state.last_eq_levels = list(temp)
                    state.broadcast_from_thread(f"EQ:{eq_ws_str}")
                    if state.loop and state.serial_queue:
                        state.loop.call_soon_threadsafe(state.serial_queue.put_nowait, f"eq {eq_str}")
                time.sleep(0.02)
            except Exception:
                time.sleep(1.0)
        return

    proc = None
    smoothed_levels = [0.0] * 8
    
    while True:
        try:
            active = False
            actions = actions_ref[0]
            if actions and "modes" in actions:
                current_mode = actions.get("current_mode", "Default")
                if current_mode in actions["modes"]:
                    led_config = actions["modes"][current_mode].get("led", {})
                    if led_config.get("effect") == "equalizer":
                        active = True
            
            if not active or state.flashing_active:
                if proc:
                    try:
                        proc.terminate()
                        proc.wait()
                    except Exception:
                        pass
                    proc = None
                time.sleep(0.5)
                continue
                
            if proc is None:
                print("[eq] starting parec capture...")
                proc = subprocess.Popen(
                    ["parec", "-d", "@DEFAULT_SINK@.monitor", "--format=s16le", "--channels=1", "--rate=22050"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL
                )
                time.sleep(0.1)
                
            chunk_size = 512
            data = proc.stdout.read(chunk_size)
            if not data:
                proc.terminate()
                proc.wait()
                proc = None
                time.sleep(0.5)
                continue
                
            num_samples = len(data) // 2
            if num_samples >= 256:
                samples = struct.unpack(f"<256h", data[:512])
                complex_samples = [(float(s) / 32768.0, 0.0) for s in samples]
                spectrum = fft(complex_samples)
                
                temp = [0] * 8
                for b in range(8):
                    start, end = bands_bins[b]
                    mag_sum = 0.0
                    for k in range(start, end + 1):
                        r, i = spectrum[k]
                        mag_sum += math.sqrt(r * r + i * i)
                    avg_mag = mag_sum / (end - start + 1)
                    
                    scale = bands_scales[b]
                    x = max(0.0, min(1.0, avg_mag * scale))
                    val = int(100 * (x ** 0.5))
                    
                    smoothed_levels[b] = smoothed_levels[b] * 0.65 + val * 0.35
                    temp[b] = int(smoothed_levels[b])
                
                eq_str = " ".join(map(str, temp))
                eq_ws_str = ":".join(map(str, temp))
                
                state.last_eq_levels = list(temp)
                state.broadcast_from_thread(f"EQ:{eq_ws_str}")
                if state.loop and state.serial_queue:
                    state.loop.call_soon_threadsafe(state.serial_queue.put_nowait, f"eq {eq_str}")
                    
        except Exception as e:
            print(f"[eq] error in watcher loop: {e}")
            if proc:
                try:
                    proc.terminate()
                    proc.wait()
                except Exception:
                    pass
                proc = None
            time.sleep(1.0)
