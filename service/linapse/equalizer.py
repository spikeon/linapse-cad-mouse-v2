import sys
import time
import subprocess
import struct
import math
from . import state

class AudioFilter:
    def __init__(self):
        self.lp_state = 0.0
        self.hp_state = 0.0
        self.hp_prev_x = 0.0

    def process(self, samples):
        bass_sum = 0.0
        treble_sum = 0.0
        
        lp = self.lp_state
        hp = self.hp_state
        prev_x = self.hp_prev_x
        
        for x in samples:
            # Lowpass (Bass, cutoff ~200Hz at 22050Hz sample rate)
            lp = lp + 0.057 * (x - lp)
            bass_sum += abs(lp)
            
            # Highpass (Treble, cutoff ~4000Hz at 22050Hz sample rate)
            hp = 0.46 * (hp + x - prev_x)
            prev_x = x
            treble_sum += abs(hp)
            
        self.lp_state = lp
        self.hp_state = hp
        self.hp_prev_x = prev_x
        
        n = len(samples) or 1
        return bass_sum / n, treble_sum / n

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
                    phase += 0.03
                    bass = int(50 + 50 * math.sin(phase))
                    treble = int(50 + 50 * math.cos(phase * 1.5))
                    state.last_bass_level = bass
                    state.last_treble_level = treble
                    state.broadcast_from_thread(f"EQ:{bass}:{treble}")
                    if state.loop and state.serial_queue:
                        state.loop.call_soon_threadsafe(state.serial_queue.put_nowait, f"eq {bass} {treble}")
                time.sleep(0.015)
            except Exception:
                time.sleep(1.0)
        return

    proc = None
    audio_filter = AudioFilter()
    
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
            if num_samples > 0:
                samples = struct.unpack(f"<{num_samples}h", data[:num_samples*2])
                bass_avg, treble_avg = audio_filter.process(samples)
                
                if bass_avg < 150.0:
                    bass_level = 0
                else:
                    x_bass = max(0.0, min(1.0, (bass_avg - 150.0) / 4850.0))
                    bass_level = int(10 + 90 * (x_bass ** 0.4))

                if treble_avg < 100.0:
                    treble_level = 0
                else:
                    x_treb = max(0.0, min(1.0, (treble_avg - 100.0) / 2400.0))
                    treble_level = int(10 + 90 * (x_treb ** 0.4))
                
                state.last_bass_level = bass_level
                state.last_treble_level = treble_level
                state.broadcast_from_thread(f"EQ:{bass_level}:{treble_level}")
                if state.loop and state.serial_queue:
                    state.loop.call_soon_threadsafe(state.serial_queue.put_nowait, f"eq {bass_level} {treble_level}")
                    
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
