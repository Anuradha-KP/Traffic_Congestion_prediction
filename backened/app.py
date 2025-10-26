import os
import pickle
from datetime import datetime, timedelta

import pandas as pd
import numpy as np
from flask import Flask, render_template, request, jsonify
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split

# -----------------------
# Config
# -----------------------
DATA_FILE = "kerala_traffic_synthetic_dataset.csv"
MODEL_FILE = "model.pkl"

app = Flask(__name__, static_folder="static", template_folder="templates")

# -----------------------
# Train model if needed
# -----------------------
def train_model():
    if not os.path.exists(DATA_FILE):
        raise FileNotFoundError(f"Dataset not found at {DATA_FILE}. Please place the CSV there.")

    data = pd.read_csv(DATA_FILE)
    data = data.dropna(subset=[
        "hour", "location", "traffic_volume", "average_speed_kmph",
        "occupancy_ratio", "day_of_week", "congestion_level"
    ])

    X = data[["hour", "location", "traffic_volume", "average_speed_kmph", "occupancy_ratio", "day_of_week"]].copy()
    y = data["congestion_level"].copy()

    X = pd.get_dummies(X, columns=["location", "day_of_week"], drop_first=False)
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    model = RandomForestClassifier(n_estimators=200, random_state=42)
    model.fit(X_train, y_train)

    with open(MODEL_FILE, "wb") as f:
        pickle.dump((model, X.columns.tolist()), f)

    print("Model trained and saved to", MODEL_FILE)

# Train if model not exists
if not os.path.exists(MODEL_FILE):
    print("Model not found. Training model now...")
    train_model()

# Load model
with open(MODEL_FILE, "rb") as f:
    model, model_columns = pickle.load(f)

# -----------------------
# Routes for Pages
# -----------------------
@app.route("/")
def home_page():
    return render_template("index.html")

@app.route("/predict")
def predict_page():
    return render_template("index.html", target="predict")

@app.route("/trend")
def trend_page():
    return render_template("index.html", target="trend")

@app.route("/compare")
def compare_page():
    return render_template("index.html", target="compare")

@app.route("/live")
def live_page():
    return render_template("index.html", target="live")

@app.route("/about")
def about_page():
    return render_template("index.html", target="about")

# -----------------------
# API: Locations
# -----------------------
@app.route("/locations")
def get_locations():
    if not os.path.exists(DATA_FILE):
        return jsonify([])
    df = pd.read_csv(DATA_FILE)
    locs = sorted(df["location"].dropna().unique().tolist())
    return jsonify(locs)

# -----------------------
# API: Predict
# -----------------------
@app.route("/api/predict", methods=["POST"])
def api_predict():
    try:
        payload = request.get_json()
        date_str = payload.get("date")
        hour = int(payload.get("hour"))
        location = str(payload.get("location"))

        df = pd.read_csv(DATA_FILE)
        subset = df[(df["location"] == location) & (df["hour"] == hour)]
        if subset.empty:
            subset = df[df["location"] == location]
        if subset.empty:
            subset = df

        traffic_volume = subset["traffic_volume"].mean() * np.random.uniform(0.8, 1.2)
        avg_speed = subset["average_speed_kmph"].mean() * np.random.uniform(0.8, 1.2)
        occupancy = min(subset["occupancy_ratio"].mean() * np.random.uniform(0.8, 1.2), 1.0)

        day_name = pd.to_datetime(date_str).day_name() if date_str else pd.to_datetime("today").day_name()

        input_row = {
            "hour": hour,
            "traffic_volume": traffic_volume,
            "average_speed_kmph": avg_speed,
            "occupancy_ratio": occupancy,
            "location": location,
            "day_of_week": day_name
        }

        input_df = pd.DataFrame([input_row])
        input_df = pd.get_dummies(input_df, columns=["location", "day_of_week"], drop_first=False)
        input_df = input_df.reindex(columns=model_columns, fill_value=0)

        pred_label = model.predict(input_df)[0]

        return jsonify({
            "congestion": pred_label,
            "speed": f"{avg_speed:.1f} km/h",
            "volume": f"{int(traffic_volume)} vehicles/hour",
            "occupancy": f"{occupancy*100:.1f} %"
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 400

# -----------------------
# API: Weekly Trend
# -----------------------
@app.route("/api/trend", methods=["POST"])
def api_trend():
    try:
        payload = request.get_json()
        date_str = payload.get("date")
        hour = int(payload.get("hour"))
        location = str(payload.get("location"))

        df = pd.read_csv(DATA_FILE)
        start_date = pd.to_datetime(date_str).date() if date_str else pd.to_datetime("today").date()
        mapping = {"Low": 0, "Medium": 1, "High": 2}
        results = []

        for i in range(7):
            day_date = start_date + timedelta(days=i)
            day_name = day_date.strftime("%A")
            subset = df[(df["location"] == location) & (df["hour"] == hour)]
            if subset.empty: subset = df[df["location"] == location]
            if subset.empty: subset = df

            traffic_volume = subset["traffic_volume"].mean() * np.random.uniform(0.8, 1.2)
            avg_speed = subset["average_speed_kmph"].mean() * np.random.uniform(0.8, 1.2)
            occupancy = min(subset["occupancy_ratio"].mean() * np.random.uniform(0.8, 1.2), 1.0)

            input_row = {
                "hour": hour,
                "location": location,
                "day_of_week": day_name,
                "traffic_volume": traffic_volume,
                "average_speed_kmph": avg_speed,
                "occupancy_ratio": occupancy
            }

            input_df = pd.DataFrame([input_row])
            input_df = pd.get_dummies(input_df, columns=["location", "day_of_week"], drop_first=False)
            input_df = input_df.reindex(columns=model_columns, fill_value=0)

            pred_label = model.predict(input_df)[0]
            intensity = (traffic_volume / subset["traffic_volume"].max() + occupancy) / 2

            results.append({
                "day": day_date.strftime("%a"),
                "congestion": pred_label,
                "congestion_value": mapping.get(pred_label, 0),
                "intensity": intensity,
                "traffic_volume": traffic_volume,
                "occupancy_ratio": occupancy
            })

        return jsonify(results)

    except Exception as e:
        return jsonify({"error": str(e)}), 400

# -----------------------
# API: Compare Multiple Locations
# -----------------------
@app.route("/api/compare", methods=["POST"])
def api_compare():
    try:
        payload = request.get_json()
        date_str = payload.get("date")
        hour = int(payload.get("hour"))
        locations = payload.get("locations", [])

        if not locations:
            return jsonify({"error": "No locations provided"}), 400

        df = pd.read_csv(DATA_FILE)
        results = []

        for loc in locations:
            subset = df[(df["location"] == loc) & (df["hour"] == hour)]
            if subset.empty: subset = df[df["location"] == loc]
            if subset.empty: subset = df

            traffic_volume = subset["traffic_volume"].mean() * np.random.uniform(0.8, 1.2)
            avg_speed = subset["average_speed_kmph"].mean() * np.random.uniform(0.8, 1.2)
            occupancy = min(subset["occupancy_ratio"].mean() * np.random.uniform(0.8, 1.2), 1.0)

            day_name = pd.to_datetime(date_str).day_name() if date_str else pd.to_datetime("today").day_name()

            input_row = {
                "hour": hour,
                "location": loc,
                "day_of_week": day_name,
                "traffic_volume": traffic_volume,
                "average_speed_kmph": avg_speed,
                "occupancy_ratio": occupancy
            }

            input_df = pd.DataFrame([input_row])
            input_df = pd.get_dummies(input_df, columns=["location", "day_of_week"], drop_first=False)
            input_df = input_df.reindex(columns=model_columns, fill_value=0)

            pred_label = model.predict(input_df)[0]

            results.append({
                "location": loc,
                "congestion": pred_label,
                "traffic_volume": int(traffic_volume),
                "average_speed_kmph": round(avg_speed,1),
                "occupancy_ratio": round(occupancy,2)
            })

        return jsonify(results)

    except Exception as e:
        return jsonify({"error": str(e)}), 400

# -----------------------
# API: Live Data Simulation
# -----------------------
@app.route("/api/live")
def api_live():
    try:
        df = pd.read_csv(DATA_FILE)
        sample = df.sample(10)
        live_data = []
        for _, row in sample.iterrows():
            live_data.append({
                "timestamp": datetime.now().strftime("%H:%M:%S"),
                "location": row["location"],
                "predicted_congestion": np.random.choice(["Low","Medium","High"], p=[0.3,0.4,0.3]),
                "traffic_volume": int(row["traffic_volume"]*np.random.uniform(0.7,1.3)),
                "average_speed_kmph": round(row["average_speed_kmph"]*np.random.uniform(0.7,1.2),1),
                "occupancy_ratio": min(row["occupancy_ratio"]*np.random.uniform(0.7,1.2),1.0)
            })
        return jsonify(live_data)
    except:
        return jsonify([])

# -----------------------
# Run App
# -----------------------
if __name__ == "__main__":
    app.run(debug=True)
