"""Module STT (Speech-to-Text) pour Alex — utilise le Python système avec SpeechRecognition."""
import subprocess
import tempfile
import os
import sys


async def transcribe_audio(audio_data: bytes, language: str = "fr-FR") -> str:
    """
    Transcrit un fichier audio en texte.
    Utilise SpeechRecognition (Python système) via subprocess.
    
    Args:
        audio_data: Données audio (WebM, WAV, etc.)
        language: Code langue (défaut: fr-FR)
    
    Returns:
        Texte transcrit ou chaîne vide si échec
    """
    if not audio_data or len(audio_data) < 100:
        return ""

    # Chemin vers le script worker
    worker_path = os.path.join(os.path.dirname(__file__), "stt_worker.py")
    
    try:
        # Lancer le worker STT comme subprocess
        proc = await asyncio.create_subprocess_exec(
            sys.executable, worker_path,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(input=audio_data),
            timeout=10
        )
        
        text = stdout.decode().strip()
        return text
        
    except asyncio.TimeoutError:
        print("[STT] Timeout transcription")
        return ""
    except Exception as e:
        print(f"[STT] Erreur transcription: {e}")
        return ""


import asyncio
