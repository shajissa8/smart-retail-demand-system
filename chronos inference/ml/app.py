from flask import Flask, request, jsonify
import torch
import model
import pandas as pd

from smi_nudger import generate_smi_variables, apply_nudger_to_12weeks

torch.set_num_threads(4)
app = Flask(__name__)

# Load model once
print("Loading ML model...")
pipeline = model.load_pipeline()
print("ML model loaded successfully.")


@app.route("/predict", methods=["POST"])
def predict():
    try:
        data = request.get_json()

        values = data["values"][0]   # [[...]] → [...]
        pred_len = data.get("prediction_length", 12)

        # ─────────────────────────────
        # STEP 1: Chronos Forecast
        # ─────────────────────────────
        mean_forecast = model.forecast(pipeline, values, pred_len)

        # ─────────────────────────────
        # STEP 2: Create DataFrame
        # ─────────────────────────────
        df = pd.DataFrame({
            "Date": pd.date_range(
                end=pd.Timestamp.today(),
                periods=len(values),
                freq="W-FRI"
            ),
            "value": values
        })

        # ─────────────────────────────
        # STEP 3: Generate SMI
        # ─────────────────────────────
        smi_df = generate_smi_variables(df, "Date", "value", "W-FRI")

        # ─────────────────────────────
        # STEP 4: Forecast DF
        # ─────────────────────────────
        forecast_df = pd.DataFrame({
            "Demand": mean_forecast,
            "Period": [f"Week {i+1}" for i in range(pred_len)]
        })

        # ─────────────────────────────
        # STEP 5: Apply Nudger
        # ─────────────────────────────
        nudged_df = apply_nudger_to_12weeks(forecast_df, smi_df)

        # ─────────────────────────────
        # STEP 6: Return
        # ─────────────────────────────
        return jsonify({
            "baseline": mean_forecast,
            "nudged": nudged_df["nudged_demand"].tolist(),
            "multipliers": nudged_df["multiplier"].tolist()
        })

    except Exception as e:
        print("FLASK ERROR:", repr(e))
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    print("Starting Flask server...")
    app.run(port=5001)
