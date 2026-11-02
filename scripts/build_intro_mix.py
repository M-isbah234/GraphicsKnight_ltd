import asyncio
import edge_tts
import scipy.io.wavfile as wav
import scipy.signal as signal
import numpy as np
import lameenc

rate = 44100

# 1. Load the original full audio (9.5s)
import pygame, pygame.sndarray
pygame.mixer.init()
s_orig = pygame.mixer.Sound('original_mehak_intro.mp3')
orig_data = pygame.sndarray.array(s_orig) # (418950, 2)
total_samples = len(orig_data)

# 2. Extract clean music for the full 9.5s
# Seg 0-3.5s has vocal in center -> apply spectral suppression
# Seg 3.5s-end is already clean music!
clean_music = np.copy(orig_data).astype(float)

split_idx = int(3.5 * rate)
L = orig_data[:split_idx, 0].astype(float)
R = orig_data[:split_idx, 1].astype(float)

f, t_stft, Zxx_L = signal.stft(L, fs=rate, nperseg=2048, noverlap=1536)
_, _, Zxx_R = signal.stft(R, fs=rate, nperseg=2048, noverlap=1536)

diff_mag = np.abs(Zxx_L - Zxx_R)
sum_mag = np.abs(Zxx_L) + np.abs(Zxx_R) + 1e-6
side_ratio = diff_mag / sum_mag

freq_mask = (f >= 100) & (f <= 5000)
mask = np.ones_like(Zxx_L, dtype=float)
for i in range(len(f)):
    if freq_mask[i]:
        mask[i, :] = np.clip(side_ratio[i, :] * 2.2, 0.0, 1.0)

clean_L = Zxx_L * mask
clean_R = Zxx_R * mask

_, rec_L = signal.istft(clean_L, fs=rate, nperseg=2048, noverlap=1536)
_, rec_R = signal.istft(clean_R, fs=rate, nperseg=2048, noverlap=1536)

clean_music[:split_idx, 0] = rec_L[:split_idx]
clean_music[:split_idx, 1] = rec_R[:split_idx]

# Smooth the split point with a 50ms crossfade
xf_len = int(0.05 * rate)
xf_in = np.linspace(0, 1, xf_len)[:, np.newaxis]
clean_music[split_idx-xf_len:split_idx] = (
    clean_music[split_idx-xf_len:split_idx] * (1 - xf_in) +
    orig_data[split_idx-xf_len:split_idx] * xf_in
)

print("Full clean music ready. Shape:", clean_music.shape)

# 3. Simple acoustic reverb impulse response (early reflections + decaying tail)
rev_len = int(0.65 * rate)
t_rev = np.linspace(0, 0.65, rev_len)
# exponential decay with random reflections
np.random.seed(42)
rev_L = np.exp(-5.5 * t_rev) * (np.random.randn(rev_len) * 0.5)
rev_R = np.exp(-5.5 * t_rev) * (np.random.randn(rev_len) * 0.5)
# stereo separation
rev_L[:int(0.015*rate)] *= 0.2
rev_R[:int(0.025*rate)] *= 0.2
rev_L[0] = 1.0
rev_R[0] = 1.0

def apply_studio_chain(raw_mono):
    # EQ: high-pass 80Hz, boost 160Hz warmth
    sos_hp = signal.butter(2, 80, 'hp', fs=rate, output='sos')
    sos_warmth = signal.butter(2, [120, 220], 'bandpass', fs=rate, output='sos')
    
    hp_sound = signal.sosfilt(sos_hp, raw_mono)
    warm_sound = signal.sosfilt(sos_warmth, raw_mono) * 0.4
    
    eq_voice = hp_sound + warm_sound
    
    # Normalize voice peak
    eq_voice = eq_voice / (np.max(np.abs(eq_voice)) + 1e-6) * 22000.0
    
    # Apply reverb
    v_L = signal.fftconvolve(eq_voice, rev_L)[:len(eq_voice)]
    v_R = signal.fftconvolve(eq_voice, rev_R)[:len(eq_voice)]
    
    stereo_voice = np.column_stack([
        eq_voice * 0.85 + v_L * 0.15,
        eq_voice * 0.85 + v_R * 0.15
    ])
    return stereo_voice

async def build_mix(voice_name, rate_str, pitch_str, out_mp3):
    # Generate speech
    tmp_speech = f"tmp_{voice_name}.mp3"
    comm = edge_tts.Communicate("Welcome to Shifa Studios.", voice_name, rate=rate_str, pitch=pitch_str)
    await comm.save(tmp_speech)
    
    s = pygame.mixer.Sound(tmp_speech)
    raw_arr = pygame.sndarray.array(s)
    raw_mono = raw_arr.mean(axis=1) if raw_arr.ndim > 1 else raw_arr
    
    proc_voice = apply_studio_chain(raw_mono)
    
    # Voice start time: 0.45s (gives music 450ms to swell)
    v_start = int(0.45 * rate)
    v_end = v_start + len(proc_voice)
    
    # Mix into music with gentle ducking
    mix = np.copy(clean_music)
    
    # Duck music by 2.0 dB (factor 0.8) during speech
    duck_curve = np.ones(len(mix))
    duck_ramp = int(0.2 * rate)
    duck_curve[v_start : min(len(mix), v_end)] = 0.82
    # smooth duck curve
    duck_curve = signal.convolve(duck_curve, np.hanning(duck_ramp)/np.sum(np.hanning(duck_ramp)), mode='same')
    
    mix[:, 0] *= duck_curve
    mix[:, 1] *= duck_curve
    
    # Add voice
    actual_end = min(len(mix), v_end)
    voice_slice = proc_voice[:actual_end - v_start]
    mix[v_start:actual_end, :] += voice_slice
    
    # Master limiter / normalizer
    peak = np.max(np.abs(mix))
    target_peak = 30000.0
    if peak > target_peak:
        mix = mix * (target_peak / peak)
        
    mix_int16 = np.clip(mix, -32767, 32767).astype(np.int16)
    
    # Encode with lameenc to MP3 (192kbps stereo 44.1kHz)
    encoder = lameenc.Encoder()
    encoder.set_bit_rate(192)
    encoder.set_in_sample_rate(rate)
    encoder.set_channels(2)
    encoder.set_quality(2) # high quality
    
    # Interleaved PCM for lameenc
    interleaved = mix_int16.flatten().tobytes()
    mp3_data = encoder.encode(interleaved)
    mp3_data += encoder.flush()
    
    with open(out_mp3, 'wb') as f:
        f.write(mp3_data)
        
    print(f"Mastered intro written to {out_mp3}: {len(mp3_data)} bytes")

asyncio.run(build_mix("en-US-GuyNeural", "-4%", "-2Hz", "audio/intro.mp3"))
