# ml_classifier.py
import os
import joblib
import pandas as pd
from typing import Tuple, Optional
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report

MODEL_PATH = os.environ.get("ML_MODEL_PATH", "model.joblib")
DATA_PATH = os.environ.get("ML_DATA_PATH", "ml_training_data.csv")

_model: Optional[Pipeline] = None  # lazy-loaded singleton


def _build_pipeline() -> Pipeline:
    return Pipeline([
        ("tfidf", TfidfVectorizer(ngram_range=(1, 2), stop_words="english")),
        ("clf", LogisticRegression(max_iter=1000))
    ])


def train_model() -> None:
    df = pd.read_csv(DATA_PATH)
    df = df.dropna(subset=["memo", "account"])
    X = df["memo"]
    y = df["account"]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    pipeline = _build_pipeline()
    pipeline.fit(X_train, y_train)

    y_pred = pipeline.predict(X_test)
    print(classification_report(y_test, y_pred))

    joblib.dump(pipeline, MODEL_PATH)
    print(f"[ML] Model saved to {MODEL_PATH}")


def load_model(reload: bool = False) -> Pipeline:
    global _model
    if _model is not None and not reload:
        return _model
    if not os.path.exists(MODEL_PATH):
        raise FileNotFoundError(
            f"Model file not found at {MODEL_PATH}. Train first by running train_model()."
        )
    _model = joblib.load(MODEL_PATH)
    return _model


def classify_memo(memo: str) -> str:
    model = load_model()
    return model.predict([memo])[0]


def classify_with_proba(memo: str) -> Tuple[str, float]:
    """
    Returns (predicted_label, confidence 0..1)
    """
    model = load_model()
    if hasattr(model, "predict_proba"):
        probs = model.predict_proba([memo])[0]
        idx = probs.argmax()
        label = model.classes_[idx]
        conf = float(probs[idx])
        return label, conf
    # fallback if predict_proba not available
    label = model.predict([memo])[0]
    return label, 0.5


if __name__ == "__main__":
    train_model()
