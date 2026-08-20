import os
import sys
import yaml
import whisper


def load_config(config_path="config.yaml"):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    full_path = os.path.join(script_dir, config_path)
    with open(full_path, "r") as f:
        return yaml.safe_load(f)


def transcribe_video(config):
    base_path = config["base_path"]
    filename = config["filename"]
    model_name = config.get("model", "base")
    language = config.get("language", "es")
    output_format = config.get("output_format", "txt")

    mov_path = os.path.join(base_path, f"{filename}.mov")

    if not os.path.exists(mov_path):
        print(f"Error: No se encontro el archivo {mov_path}")
        sys.exit(1)

    print(f"Cargando modelo '{model_name}'...")
    model = whisper.load_model(model_name)

    print(f"Transcribiendo: {mov_path}")
    options = {}
    if language and language != "auto":
        options["language"] = language

    result = model.transcribe(mov_path, **options)

    output_path = os.path.join(base_path, f"{filename}.{output_format}")

    if output_format == "txt":
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(result["text"])
    elif output_format == "srt":
        with open(output_path, "w", encoding="utf-8") as f:
            for i, seg in enumerate(result["segments"], 1):
                start = format_timestamp(seg["start"])
                end = format_timestamp(seg["end"])
                f.write(f"{i}\n{start} --> {end}\n{seg['text'].strip()}\n\n")
    elif output_format == "vtt":
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("WEBVTT\n\n")
            for seg in result["segments"]:
                start = format_timestamp(seg["start"])
                end = format_timestamp(seg["end"])
                f.write(f"{start} --> {end}\n{seg['text'].strip()}\n\n")

    print(f"Transcripcion guardada en: {output_path}")


def format_timestamp(seconds):
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds - int(seconds)) * 1000)
    return f"{hrs:02d}:{mins:02d}:{secs:02d},{millis:03d}"


if __name__ == "__main__":
    config = load_config()
    transcribe_video(config)
