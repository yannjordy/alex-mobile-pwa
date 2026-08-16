#!/usr/bin/env python3
"""Script STT simple — lit audio sur stdin (WebM/OGG/etc), écrit le texte sur stdout."""
import sys
import speech_recognition as sr
import tempfile
import os
import subprocess

def main():
    audio_data = sys.stdin.buffer.read()
    
    if not audio_data or len(audio_data) < 100:
        print("")
        return
    
    tmp_in = None
    tmp_wav = None
    try:
        # Sauvegarder l'audio d'entrée (WebM/Opus)
        tmp_in = tempfile.NamedTemporaryFile(suffix=".webm", delete=False)
        tmp_in.write(audio_data)
        tmp_in.close()
        
        # Convertir en WAV 16kHz mono avec ffmpeg
        tmp_wav_path = tmp_in.name + ".wav"
        result = subprocess.run(
            ["ffmpeg", "-y", "-i", tmp_in.name, "-ar", "16000", "-ac", "1", "-f", "wav", tmp_wav_path],
            capture_output=True, timeout=5
        )
        
        if result.returncode != 0 or not os.path.exists(tmp_wav_path):
            print("")
            return
        
        # Transcrire avec Google
        r = sr.Recognizer()
        with sr.AudioFile(tmp_wav_path) as source:
            audio = r.record(source)
        
        text = r.recognize_google(audio, language="fr-FR")
        print(text)
    except sr.UnknownValueError:
        print("")
    except Exception as e:
        print("", file=sys.stderr)
        print("")
    finally:
        for p in [tmp_in.name if tmp_in else None, tmp_wav_path if 'tmp_wav_path' in dir() else None]:
            if p:
                try: os.unlink(p)
                except: pass

if __name__ == "__main__":
    main()
