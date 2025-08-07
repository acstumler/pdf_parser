import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report
import joblib
import os

MODEL_PATH = "model.joblib"
DATA_PATH = "ml_training_data.csv"

# Training function
def train_model():
    df = pd.read_csv(DATA_PATH)
    df = df.dropna(subset=["memo", "account"])  # clean

    X = df["memo"]
    y = df["account"]

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    pipeline = Pipeline([
        ("tfidf", TfidfVectorizer(ngram_range=(1, 2), stop_words="english")),
        ("clf", LogisticRegression(max_iter=1000))
    ])

    pipeline.fit(X_train, y_train)

    y_pred = pipeline.predict(X_test)
    print(classification_report(y_test, y_pred))

    joblib.dump(pipeline, MODEL_PATH)
    print(f"[ML] Model saved to {MODEL_PATH}")

# Prediction function
def load_model():
    if not os.path.exists(MODEL_PATH):
        raise FileNotFoundError("Model file not found. Run train_model() first.")
    return joblib.load(MODEL_PATH)

def classify_memo(memo):
    model = load_model()
    prediction = model.predict([memo])[0]
    return prediction

if __name__ == "__main__":
    train_model()
