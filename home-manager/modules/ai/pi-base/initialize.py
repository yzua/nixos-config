#!/usr/bin/env python3
"""Initialize Pi once while preserving credentials and later interactive settings."""

import argparse
import copy
import fcntl
import json
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path


def read_json(path):
    return json.loads(path.read_text()) if path.exists() else {}


def write_json(path, value):
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w") as stream:
            json.dump(value, stream, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def initialize(agent_dir, state_dir, policy):
    state_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(state_dir, 0o700)
    with (state_dir / "initialize.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        marker = state_dir / "initialized-v1.json"
        if marker.exists():
            print("Pi defaults already initialized; preserving interactive settings.")
            return

        defaults = policy["settings"]
        descriptor = policy["model"]
        metadata = descriptor["metadata"]
        target = metadata["id"]
        if defaults.get("defaultModel") != target:
            raise ValueError("Initialization settings.defaultModel must match model.metadata.id")

        agent_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        settings_path = agent_dir / "settings.json"
        models_path = agent_dir / "models.json"
        if settings_path.is_symlink() or models_path.is_symlink():
            raise ValueError(
                "Pi settings.json and models.json must be writable files, not managed symlinks"
            )
        settings = read_json(settings_path)
        models = read_json(models_path)
        if not isinstance(settings, dict) or not isinstance(models, dict):
            raise ValueError("Pi settings and models must contain JSON objects")

        provider = models.get("providers", {}).get(settings.get("defaultProvider"))
        model_changed = False
        if provider and not any(model.get("id") == target for model in provider.get("models", [])):
            if provider.get("api") != descriptor["api"]:
                raise ValueError(
                    f"The selected custom provider must use {descriptor['api']} for {metadata['name']}"
                )
            candidates = provider.get("models", [])
            source = next(
                (model for model in candidates if model.get("id") == settings.get("defaultModel")),
                None,
            )
            if source is None:
                raise ValueError(
                    "Configure a model for the selected provider before initializing Pi"
                )
            model = copy.deepcopy(source)
            model.update(copy.deepcopy(metadata))
            # Retain the custom endpoint's existing token limits and compatibility flags.
            provider["models"].append(model)
            model_changed = True

        extensions = list(settings.get("extensions", []))
        for extension in defaults.get("extensions", []):
            opposite = "+" + extension[1:] if extension.startswith("-") else None
            if opposite in extensions:
                extensions.remove(opposite)
            if extension not in extensions:
                extensions.append(extension)
        settings.update({key: value for key, value in defaults.items() if key != "extensions"})
        settings["extensions"] = extensions

        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
        backup_dir = state_dir / "backups" / stamp
        backup_dir.mkdir(parents=True, mode=0o700)
        for path in (settings_path, models_path):
            if path.exists():
                backup = backup_dir / path.name
                shutil.copyfile(path, backup)
                os.chmod(backup, 0o600)
        if model_changed:
            write_json(models_path, models)
        write_json(settings_path, settings)
        write_json(marker, {"backup": str(backup_dir), "model": target})
        print(f"Initialized Pi defaults. Previous settings/models saved in {backup_dir}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--agent-dir", type=Path, required=True)
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--defaults", type=Path, required=True)
    arguments = parser.parse_args()
    initialize(arguments.agent_dir, arguments.state_dir, read_json(arguments.defaults))


if __name__ == "__main__":
    main()
