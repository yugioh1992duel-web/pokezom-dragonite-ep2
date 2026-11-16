import subprocess, numpy as np, os

SR = 48000
B = os.path.dirname(os.path.abspath(__file__))
CRIES = os.path.join(B, 'assets', 'cries')
SFX = '/home/hatch/workspace/your_files/pokezom_sfx_starter_pack'
BGM = '/home/hatch/workspace/pokezom_kaiju_build/assets/bgm/final_battle_rival.mp3'

def load(path, sr=SR):
    raw = subprocess.check_output(['ffmpeg', '-v', 'error', '-i', path, '-ac', '2', '-ar', str(sr), '-f', 'f32le', '-'])
    return np.frombuffer(raw, dtype=np.float32).reshape(-1, 2).copy()

# VO used EXACTLY as delivered (user's standing rule: never cut/trim/splice VO)
vo = load(os.path.join(B, 'audio', 'vo_main_take.wav'))
DUR = len(vo) / SR
mix = vo.copy()

# BGM bed at 0.08, looped to length, 3s fade-out
bgm = load(BGM)
reps = int(np.ceil(len(mix) / len(bgm)))
bed = np.tile(bgm, (reps, 1))[:len(mix)] * 0.08
fade = int(3 * SR)
bed[-fade:] *= np.linspace(1, 0, fade)[:, None]
mix += bed

# whoosh: FFT-band noise sweep (low -> high), 0.7s (Ep.1 recipe)
rng = np.random.default_rng(7)
n = int(0.7 * SR)
noise = rng.standard_normal(n).astype(np.float32)
F = np.fft.rfft(noise); freqs = np.fft.rfftfreq(n, 1 / SR)
swept = np.zeros(n, dtype=np.float32)
steps = 24
for k in range(steps):
    s0, s1 = k * n // steps, (k + 1) * n // steps
    fc = 300 * (2400 / 300) ** (k / (steps - 1))
    band = np.exp(-0.5 * ((freqs - fc) / (fc * 0.55)) ** 2)
    seg = np.fft.irfft(F * band, n)
    env = np.sin(np.pi * (k + 0.5) / steps) ** 1.5
    swept[s0:s1] = seg[s0:s1] * env
swept /= (np.abs(swept).max() + 1e-9)
whoosh = np.stack([swept, swept], axis=1)

def place(arr, at, gain):
    i = int(at * SR)
    j = min(len(mix), i + len(arr))
    mix[i:j] += arr[:j - i] * gain

# cries on form reveals (gain 0.28, Ep.1 standard)
place(load(f'{CRIES}/147.ogg'), 38.6, 0.28)    # Dratini reveal
place(load(f'{CRIES}/148.ogg'), 99.3, 0.28)    # Dragonair reveal
place(load(f'{CRIES}/149.ogg'), 169.1, 0.28)   # Dragonite reveal
place(load(f'{CRIES}/149.ogg'), 367.0, 0.28)   # Mega Dragonite reveal
# whoosh on the sixteen-hours launch (abs 247.84)
place(whoosh, 247.84, 0.3)
# accents
place(load(f'{SFX}/level_up.ogg'), 168.9, 0.45)            # evolution into Dragonite
place(load(f'{SFX}/level_up.ogg'), 489.0, 0.5)             # Mega ranked #1
place(load(f'{SFX}/stat_up.ogg'), 399.1, 0.45)             # 600 -> 700 counter
place(load(f'{SFX}/hit_super_effective.ogg'), 210.88, 0.5) # Multiscale line
for t in (443.34, 449.64, 458.74, 465.94, 478.94, 489.04): # ranking hits
    place(load(f'{SFX}/ui_select.ogg'), t, 0.4)

# --- v2 additions (user scope expansion, Nov 16) ---
# Shadow reveal: corrupted Dragonite cry (pitch-down + reverb), gain 0.28 like other reveals
place(load(f'{CRIES}/149_shadow.wav'), 323.9, 0.28)
# Giant's singing call from EP013 (official audio), ducked under the "singing cry" line (~296.98s)
call = load(os.path.join(B, 'assets', 'giant_call.wav')).copy()
fi, fo = int(1.2 * SR), int(2.2 * SR)
call[:fi] *= np.linspace(0, 1, fi)[:, None]
call[-fo:] *= np.linspace(1, 0, fo)[:, None]
place(call, 296.6, 0.20)

peak = np.abs(mix).max()
print('pre-norm peak:', round(float(peak), 3), 'duration:', round(DUR, 2))
if peak > 0.98: mix *= 0.98 / peak
p = subprocess.run(['ffmpeg', '-y', '-v', 'error', '-f', 'f32le', '-ar', str(SR), '-ac', '2', '-i', '-', '-c:a', 'pcm_s16le', os.path.join(B, 'mix_v2.wav')], input=mix.astype(np.float32).tobytes())
assert p.returncode == 0
print('mix_v2.wav written')
