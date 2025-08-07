import os
import subprocess

EXPORT_SCRIPT = "export_memory_to_csv.py"
TRAIN_SCRIPT = "ml_classifier.py"

print("[Retrain] Exporting vendor memory to training CSV...")
subprocess.run(["python", EXPORT_SCRIPT])

print("[Retrain] Training ML classifier on updated dataset...")
subprocess.run(["python", TRAIN_SCRIPT])

print("[Retrain] Done.")
