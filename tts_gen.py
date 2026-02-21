import inspect
import io
import logging
import re
import time
import unicodedata
from pathlib import Path
from typing import Any, Callable

import numpy as np
import soundfile as sf
import torch
from num2words import num2words
from scipy.signal import resample_poly

from config import Config

logger = logging.getLogger(__name__)

URL_RE = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
HANDLE_RE = re.compile(r"(?<!\w)@[A-Za-z0-9_]{2,}(?!\w)")
NUMBER_RE = re.compile(r"(?<!\w)([-+]?\d+(?:[.,]\d+)?)(?!\w)")
LATIN_WORD_RE = re.compile(r"[A-Za-z]+")
MARKDOWN_CONTROL_RE = re.compile(r"[_*\[\]()~`>#+=|{}\\]")
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?;:])\s+")
MULTI_SPACE_RE = re.compile(r"\s+")

MAX_CHUNK_CHARS = 220
PAUSE_MS_BETWEEN_CHUNKS = 140
TARGET_PEAK = 0.95
FADE_MS = 8.0
SOFT_LIMIT = 0.98

LATIN_TO_CYRILLIC = {
    "a": "а",
    "b": "б",
    "c": "ц",
    "d": "д",
    "e": "е",
    "f": "ф",
    "g": "г",
    "h": "х",
    "i": "и",
    "j": "й",
    "k": "к",
    "l": "л",
    "m": "м",
    "n": "н",
    "o": "о",
    "p": "п",
    "q": "к",
    "r": "р",
    "s": "с",
    "t": "т",
    "u": "у",
    "v": "в",
    "w": "в",
    "x": "кс",
    "y": "й",
    "z": "з",
}


def _try_load_silero_stress(required: bool = True) -> Callable[[str], str]:
    try:
        from silero_stress import load_accentor  # type: ignore
    except Exception as exc:
        if required:
            raise RuntimeError(
                "silero-stress is required for voice generation. Install silero-stress==1.4."
            ) from exc
        return lambda text: text

    try:
        accentor = load_accentor()
    except Exception as exc:
        if required:
            raise RuntimeError("Failed to initialize silero-stress accentor.") from exc
        return lambda text: text

    if not callable(accentor):
        raise RuntimeError("silero-stress load_accentor() did not return a callable accentor.")

    return accentor


def _is_speak_xml(text: str) -> bool:
    stripped = text.strip()
    return stripped.startswith("<speak>") and stripped.endswith("</speak>")


def _latin_word_to_cyrillic(word: str) -> str:
    return "".join(LATIN_TO_CYRILLIC.get(ch.lower(), ch) for ch in word)


def _number_to_russian(match: re.Match[str]) -> str:
    token = match.group(1)
    normalized = token.replace(",", ".")

    try:
        value = float(normalized)
    except ValueError:
        return token

    if "." in normalized:
        integer_part = int(value)
        fractional_raw = normalized.split(".", 1)[1].rstrip("0")
        if not fractional_raw:
            return num2words(integer_part, lang="ru")
        fractional_part = int(fractional_raw)
        return (
            f"{num2words(integer_part, lang='ru')} целых "
            f"{num2words(fractional_part, lang='ru')}"
        )

    return num2words(int(value), lang="ru")


def _split_long_sentence(sentence: str, max_chars: int) -> list[str]:
    words = sentence.split()
    if not words:
        return []

    chunks: list[str] = []
    current: list[str] = []

    for word in words:
        proposal = " ".join(current + [word]).strip()
        if len(proposal) <= max_chars or not current:
            current.append(word)
            continue
        chunks.append(" ".join(current).strip())
        current = [word]

    if current:
        chunks.append(" ".join(current).strip())

    return chunks


def _chunk_text(text: str, max_chars: int = MAX_CHUNK_CHARS) -> list[str]:
    if len(text) <= max_chars:
        return [text]

    sentences = [part.strip() for part in SENTENCE_SPLIT_RE.split(text) if part.strip()]
    if not sentences:
        return [text[:max_chars]]

    chunks: list[str] = []
    current = ""

    for sentence in sentences:
        if len(sentence) > max_chars:
            if current:
                chunks.append(current.strip())
                current = ""
            chunks.extend(_split_long_sentence(sentence, max_chars))
            continue

        candidate = f"{current} {sentence}".strip() if current else sentence
        if len(candidate) <= max_chars:
            current = candidate
        else:
            chunks.append(current.strip())
            current = sentence

    if current:
        chunks.append(current.strip())

    return [chunk for chunk in chunks if chunk]


def _fade_in_out(audio: np.ndarray, sample_rate: int, fade_ms: float = FADE_MS) -> np.ndarray:
    if audio.size == 0:
        return audio

    n = audio.shape[0]
    k = int(sample_rate * fade_ms / 1000.0)
    if k <= 1 or n < 2 * k:
        return audio

    window = np.linspace(0.0, 1.0, k, dtype=np.float32)
    faded = audio.copy()
    faded[:k] *= window
    faded[-k:] *= window[::-1]
    return faded


def _remove_dc(audio: np.ndarray) -> np.ndarray:
    if audio.size == 0:
        return audio
    return audio - np.mean(audio, dtype=np.float32)


def _peak_normalize(audio: np.ndarray, peak: float = TARGET_PEAK) -> np.ndarray:
    if audio.size == 0:
        return audio

    max_abs = float(np.max(np.abs(audio)))
    if max_abs <= 1e-9:
        return audio

    return audio * (peak / max_abs)


def _soft_limit(audio: np.ndarray, limit: float = SOFT_LIMIT) -> np.ndarray:
    if audio.size == 0:
        return audio

    max_abs = float(np.max(np.abs(audio)))
    if max_abs <= limit:
        return audio

    clipped = np.clip(audio, -1.0, 1.0)
    return np.tanh(clipped / limit) * limit


def _to_mono_float32(audio: np.ndarray) -> np.ndarray:
    if audio.size == 0:
        return np.asarray(audio, dtype=np.float32)

    arr = np.asarray(audio, dtype=np.float32)
    if arr.ndim == 1:
        return arr
    if arr.ndim == 2:
        return np.mean(arr, axis=1, dtype=np.float32)

    return np.reshape(arr, (-1,)).astype(np.float32, copy=False)


class TTSGenerator:
    def __init__(self, sample_rate: int):
        if sample_rate <= 0:
            raise ValueError("sample_rate must be > 0")

        self.target_sample_rate = int(sample_rate)
        self.device = "cpu"
        self.put_accent = True
        self.put_yo = True

        torch.set_num_threads(4)

        local_file = Config.SILERO_LOCAL_PATH
        if not local_file:
            raise RuntimeError("SILERO_LOCAL_PATH is required for TTS initialization.")

        self.model_path = Path(local_file)
        if not self.model_path.is_file():
            self.model_path.parent.mkdir(parents=True, exist_ok=True)
            torch.hub.download_url_to_file(
                "https://models.silero.ai/models/tts/ru/v4_ru.pt", str(self.model_path)
            )

        if not self.model_path.is_file():
            raise RuntimeError(f"Silero model file is missing: {self.model_path}")

        self.model = torch.package.PackageImporter(str(self.model_path)).load_pickle(
            "tts_models", "model"
        )
        if self.model is None:
            raise RuntimeError("Failed to load Silero model from PackageImporter.")

        if hasattr(self.model, "to"):
            moved = self.model.to(self.device)
            if moved is not None:
                self.model = moved
        if hasattr(self.model, "eval"):
            evaluated = self.model.eval()
            if evaluated is not None:
                self.model = evaluated

        if not hasattr(self.model, "apply_tts") or not callable(self.model.apply_tts):
            raise RuntimeError("Loaded Silero model does not expose callable apply_tts.")

        if not hasattr(self.model, "speakers"):
            raise RuntimeError("Loaded Silero model does not expose speakers list.")

        self.speakers = list(self.model.speakers)
        if not self.speakers:
            raise RuntimeError("Silero speakers list is empty.")

        self.apply_tts: Callable[..., Any] = self.model.apply_tts
        self.apply_tts_signature = inspect.signature(self.apply_tts)

        detected_sr = getattr(self.model, "sample_rate", None) or getattr(
            self.model, "sampling_rate", None
        )
        self.model_sample_rate = int(detected_sr) if isinstance(detected_sr, (int, float)) else self.target_sample_rate

        self.accentor = _try_load_silero_stress(required=True)

        logger.info(
            "TTS initialized with %d voices, model_sr=%d, target_sr=%d",
            len(self.speakers),
            self.model_sample_rate,
            self.target_sample_rate,
        )

    def get_all_voices(self) -> list[str]:
        return list(self.speakers)

    def _validate_speaker(self, speaker: str) -> str:
        if speaker in self.speakers:
            return speaker

        fallback = self.speakers[0]
        logger.warning("Unknown speaker '%s'. Falling back to '%s'.", speaker, fallback)
        return fallback

    def _prepare_text(self, text: str) -> list[str]:
        if not text or not text.strip():
            raise ValueError("TTS text is empty.")

        if _is_speak_xml(text):
            return [text.strip()]

        normalized = unicodedata.normalize("NFKC", text)
        normalized = URL_RE.sub(" ссылка ", normalized)
        normalized = HANDLE_RE.sub(" упоминание ", normalized)
        normalized = normalized.replace("%", " процентов ")
        normalized = MARKDOWN_CONTROL_RE.sub(" ", normalized)
        normalized = normalized.replace("\r", " ").replace("\n", " ")
        normalized = NUMBER_RE.sub(_number_to_russian, normalized)
        normalized = LATIN_WORD_RE.sub(lambda m: _latin_word_to_cyrillic(m.group(0)), normalized)
        normalized = re.sub(r"[^\w\s.,!?;:«»\"'\-]", " ", normalized, flags=re.UNICODE)
        normalized = MULTI_SPACE_RE.sub(" ", normalized).strip()

        if not normalized:
            raise ValueError("TTS text became empty after preprocessing.")

        stressed = self.accentor(normalized)
        if not stressed or not stressed.strip():
            raise RuntimeError("silero-stress returned empty text.")

        return _chunk_text(stressed)

    def _build_apply_kwargs(self, text: str, speaker: str, sample_rate: int) -> dict[str, Any]:
        params = self.apply_tts_signature.parameters
        kwargs: dict[str, Any] = {}

        if "text" in params:
            kwargs["text"] = text
        elif "texts" in params:
            kwargs["texts"] = [text]
        else:
            raise RuntimeError(
                "apply_tts signature is incompatible: expected 'text' or 'texts'. "
                f"Signature: {self.apply_tts_signature}"
            )

        if "speaker" in params:
            kwargs["speaker"] = speaker
        if "sample_rate" in params:
            kwargs["sample_rate"] = sample_rate
        if "put_accent" in params:
            kwargs["put_accent"] = self.put_accent
        if "put_yo" in params:
            kwargs["put_yo"] = self.put_yo
        if "device" in params:
            kwargs["device"] = self.device
        if "model" in params and "texts" in kwargs:
            kwargs["model"] = self.model

        return kwargs

    def _synthesize_chunk(self, text: str, speaker: str, sample_rate: int) -> np.ndarray:
        kwargs = self._build_apply_kwargs(text=text, speaker=speaker, sample_rate=sample_rate)
        with torch.no_grad():
            generated = self.apply_tts(**kwargs)

        if isinstance(generated, torch.Tensor):
            audio = generated.detach().cpu().numpy()
        elif isinstance(generated, list) and generated and isinstance(generated[0], torch.Tensor):
            audio = generated[0].detach().cpu().numpy()
        else:
            audio = np.asarray(generated)

        return _to_mono_float32(np.squeeze(audio))

    def _postprocess_audio(self, audio: np.ndarray, sample_rate: int) -> np.ndarray:
        processed = _to_mono_float32(audio)
        processed = _remove_dc(processed)
        processed = _fade_in_out(processed, sample_rate)
        processed = _peak_normalize(processed, peak=TARGET_PEAK)
        processed = _soft_limit(processed, limit=SOFT_LIMIT)

        if sample_rate != self.target_sample_rate:
            gcd = int(np.gcd(sample_rate, self.target_sample_rate))
            up = self.target_sample_rate // gcd
            down = sample_rate // gcd
            processed = resample_poly(processed, up, down).astype(np.float32)

        return _to_mono_float32(processed)

    def generate_voice(self, text: str, speaker: str) -> io.BytesIO:
        started_at = time.perf_counter()

        safe_speaker = self._validate_speaker(speaker)
        chunks = self._prepare_text(text)

        all_parts: list[np.ndarray] = []
        pause_samples = int(self.model_sample_rate * PAUSE_MS_BETWEEN_CHUNKS / 1000.0)
        silence = np.zeros(pause_samples, dtype=np.float32)

        for idx, chunk in enumerate(chunks):
            chunk_audio = self._synthesize_chunk(
                text=chunk,
                speaker=safe_speaker,
                sample_rate=self.model_sample_rate,
            )
            all_parts.append(chunk_audio)
            if idx < len(chunks) - 1 and pause_samples > 0:
                all_parts.append(silence)

        if not all_parts:
            raise RuntimeError("No audio chunks were synthesized.")

        raw_audio = np.concatenate(all_parts).astype(np.float32, copy=False)
        processed_audio = self._postprocess_audio(raw_audio, self.model_sample_rate)

        peak_after = float(np.max(np.abs(processed_audio))) if processed_audio.size else 0.0
        duration_s = processed_audio.size / float(self.target_sample_rate)

        wav = np.clip(processed_audio, -1.0, 1.0)
        wav_i16 = (wav * 32767.0).astype(np.int16)

        buffer = io.BytesIO()
        sf.write(buffer, wav_i16, self.target_sample_rate, format="WAV", subtype="PCM_16")
        buffer.seek(0)

        logger.info(
            "Voice generated speaker=%s chunks=%d text_len=%d duration=%.2fs peak=%.4f latency=%.2fs",
            safe_speaker,
            len(chunks),
            len(text),
            duration_s,
            peak_after,
            time.perf_counter() - started_at,
        )

        return buffer

    def generate_voice_to_file(self, text: str, speaker: str, output_file: str) -> str:
        buffer = self.generate_voice(text=text, speaker=speaker)
        with open(output_file, "wb") as handle:
            handle.write(buffer.getvalue())
        return output_file
