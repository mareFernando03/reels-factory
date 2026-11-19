"""Separar la voz de la música de fondo (modelo MDX-Net Kim_Vocal_2, de los modelos públicos de UVR).

Cuando alguien habla en un reel que ya tenía una canción (los reels publicados de Ana casi
siempre la tienen), la "limpieza de ruido" no sirve: lo de fondo es música. Este modelo
separa la voz y deja la canción afuera. Corre con onnxruntime en la CPU (~1-2 s por cada
6 s de audio). Modelo en herramientas/bin/modelos/ (67 MB, fuera de git; se bajó con el OK
de Fernando el 04/10/2026):
  https://github.com/TRvlvr/model_repo/releases/download/all_public_uvr_models/Kim_Vocal_2.onnx

Uso:
    uv run python herramientas/separar.py entrada.wav voz.wav

Parámetros del modelo (los de UVR para Kim_Vocal_2): 44,1 kHz estéreo, n_fft 7680,
hop 1024, 3072 bandas, 256 cuadros por trozo, compensación 1,009.
"""

import sys
from pathlib import Path

import numpy as np

MODELO = Path(__file__).parent / "bin" / "modelos" / "Kim_Vocal_2.onnx"
SR = 44100
N_FFT, HOP, DIM_F, DIM_T = 7680, 1024, 3072, 256
COMPENSAR = 1.009
_sesion = None


def disponible():
    return MODELO.exists()


def _modelo():
    global _sesion
    if _sesion is None:
        import onnxruntime as ort
        _sesion = ort.InferenceSession(str(MODELO), providers=["CPUExecutionProvider"])
    return _sesion


def _ventana():
    n = np.arange(N_FFT)
    return 0.5 - 0.5 * np.cos(2 * np.pi * n / N_FFT)   # Hann periódica, como torch.hann_window


def _stft(x):
    """x: (canales, muestras) → (canales, N_FFT//2+1, cuadros), como torch.stft(center=True)."""
    w = _ventana()
    x = np.pad(x, ((0, 0), (N_FFT // 2, N_FFT // 2)), mode="reflect")
    cuadros = 1 + (x.shape[1] - N_FFT) // HOP
    idx = np.arange(N_FFT)[None, :] + HOP * np.arange(cuadros)[:, None]
    return np.stack([np.fft.rfft(c[idx] * w, axis=1).T for c in x])


def _istft(spec, largo):
    """Inversa de _stft (overlap-add normalizado por la ventana al cuadrado)."""
    w = _ventana()
    cuadros = spec.shape[2]
    total = N_FFT + HOP * (cuadros - 1)
    out = np.zeros((spec.shape[0], total))
    norma = np.zeros(total)
    for k in range(cuadros):
        a = k * HOP
        out[:, a:a + N_FFT] += np.fft.irfft(spec[:, :, k], n=N_FFT, axis=1) * w
        norma[a:a + N_FFT] += w ** 2
    out /= np.maximum(norma, 1e-8)
    return out[:, N_FFT // 2:N_FFT // 2 + largo]


def separar(mezcla):
    """mezcla: (2, muestras) a 44,1 kHz → voz (2, muestras)."""
    trozo = HOP * (DIM_T - 1)
    recorte = N_FFT // 2
    util = trozo - 2 * recorte
    n = mezcla.shape[1]
    relleno = util - n % util
    x = np.concatenate([np.zeros((2, recorte)), mezcla, np.zeros((2, relleno)), np.zeros((2, recorte))], axis=1)
    voz = []
    for i in range(0, n + relleno, util):
        spec = _stft(x[:, i:i + trozo])[:, :DIM_F, :]                       # (2, 3072, 256) complejo
        entrada = np.stack([spec[0].real, spec[0].imag, spec[1].real, spec[1].imag])[None].astype(np.float32)
        salida = _modelo().run(None, {"input": entrada})[0][0]             # (4, 3072, 256)
        completo = np.zeros((2, N_FFT // 2 + 1, DIM_T), np.complex128)
        completo[0, :DIM_F] = salida[0] + 1j * salida[1]
        completo[1, :DIM_F] = salida[2] + 1j * salida[3]
        ondas = _istft(completo, trozo)
        voz.append(ondas[:, recorte:-recorte])
    return np.concatenate(voz, axis=1)[:, :n] * COMPENSAR


def separar_archivo(entrada, salida):
    """WAV estéreo a 44,1 kHz → WAV estéreo con solo la voz."""
    import soundfile as sf
    x, sr = sf.read(entrada, always_2d=True)
    if sr != SR:
        raise ValueError(f"{entrada}: hace falta 44,1 kHz (tiene {sr})")
    x = x.T if x.shape[1] == 2 else np.repeat(x.T, 2, axis=0)
    sf.write(salida, separar(x).T.astype(np.float32), SR)
    return Path(salida)


if __name__ == "__main__":
    separar_archivo(sys.argv[1], sys.argv[2])
    print(f"-> {sys.argv[2]}")
