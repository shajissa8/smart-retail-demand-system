import torch
import numpy as np
import time
import os
import psutil
import json
from chronos import ChronosPipeline
from sklearn.preprocessing import MinMaxScaler


# ─────────────────────────────────────────────
# 🔹 PROFILER
# ─────────────────────────────────────────────
class ModelProfiler:
    def __init__(self):
        self.process = psutil.Process(os.getpid())
        self.start_time = None
        self.start_rss = None
        self.start_cuda = None

    def start_timer(self):
        self.start_time = time.time()
        self.start_rss = self.process.memory_info().rss

        if torch.cuda.is_available():
            torch.cuda.reset_peak_memory_stats()
            torch.cuda.synchronize()
            self.start_cuda = torch.cuda.memory_allocated()
        else:
            self.start_cuda = 0

    def end_timer(self):
        if torch.cuda.is_available():
            torch.cuda.synchronize()
            peak_cuda = torch.cuda.max_memory_allocated() - self.start_cuda
            memory_gb = peak_cuda / (1024 ** 3)
        else:
            peak_rss = self.process.memory_info().rss - self.start_rss
            memory_gb = peak_rss / (1024 ** 3)

        elapsed = time.time() - self.start_time
        return round(elapsed, 3), round(memory_gb, 3)

    def estimate_flops(self, seq_len, prediction_length=12, num_samples=20):
        seq_len = max(int(seq_len), 1)
        prediction_length = max(int(prediction_length), 1)
        num_samples = max(int(num_samples), 1)

        # Approximation
        flops = seq_len * prediction_length * num_samples * 0.002
        return round(flops, 3)


# ─────────────────────────────────────────────
# 🔹 MODEL LOADING
# ─────────────────────────────────────────────
def load_model():
    pipeline = ChronosPipeline.from_pretrained("amazon/chronos-t5-small")

    device = "cuda" if torch.cuda.is_available() else "cpu"
    pipeline.model.to(device)

    pipeline.model.eval()
    torch.set_num_threads(4)

    return pipeline


def load_pipeline():
    return load_model()


# ─────────────────────────────────────────────
# 🔹 FORECAST
# ─────────────────────────────────────────────
def forecast(pipeline, values, prediction_length=12):
    values = np.array(values, dtype=float).flatten()

    if len(values) == 0:
        return [0.0] * prediction_length

    min_val, max_val = values.min(), values.max()
    value_range = max_val - min_val

    use_log = False

    if value_range > 10_000_000 or (max_val > 5_000_000 and np.std(values) > 500_000):
        use_log = True
        log_values = np.log1p(values)
        scaler = MinMaxScaler()
        scaled = scaler.fit_transform(log_values.reshape(-1, 1)).flatten()
    else:
        scaler = MinMaxScaler()
        scaled = scaler.fit_transform(values.reshape(-1, 1)).flatten()

    history = torch.tensor(scaled, dtype=torch.float32).unsqueeze(0)

    with torch.no_grad():
        samples = pipeline.predict(
            history,
            prediction_length=prediction_length,
            num_samples=20,
            temperature=0.7,
        )

    if isinstance(samples, torch.Tensor):
        samples = samples.cpu().numpy()

    if samples.ndim == 3:
        mean_scaled = samples.mean(axis=1).squeeze()
    else:
        mean_scaled = samples.mean(axis=0)

    if use_log:
        mean_forecast = np.expm1(
            mean_scaled * (log_values.max() - log_values.min()) + log_values.min()
        )
    else:
        mean_forecast = scaler.inverse_transform(
            mean_scaled.reshape(-1, 1)
        ).flatten()

    return mean_forecast.tolist()


# ─────────────────────────────────────────────
# 🔹 MAIN EXECUTION (IMPORTANT FOR NODE)
# ─────────────────────────────────────────────
def run_forecast_with_profiling(values, prediction_length=12):
    profiler = ModelProfiler()

    # 🔹 Measure model loading (compile time)
    profiler.start_timer()
    pipeline = load_pipeline()
    compile_time, memory_gb = profiler.end_timer()

    # 🔹 Measure inference time
    start_infer = time.time()
    predictions = forecast(pipeline, values, prediction_length)
    inference_time = round(time.time() - start_infer, 3)

    # 🔹 FLOPs estimation
    flops = profiler.estimate_flops(
        seq_len=len(np.array(values).flatten()),
        prediction_length=prediction_length,
        num_samples=20
    )

    # 🔹 FINAL OUTPUT (SINGLE JSON → Node.js safe)
    output = {
        "predictions": predictions,
        "metrics": {
            "compile_time_sec": compile_time,
            "inference_time_sec": inference_time,
            "memory_gb": memory_gb,
            "flops_tf": flops
        }
    }

    print(json.dumps(output))  # ✅ IMPORTANT

    return output


# ─────────────────────────────────────────────
# 🔹 CLI ENTRY (when called from Node)
# ─────────────────────────────────────────────
if __name__ == "__main__":
    import sys

    try:
        # Expect input as JSON string from Node
        input_data = json.loads(sys.stdin.read())

        values = input_data.get("values", [])
        prediction_length = input_data.get("prediction_length", 12)

        run_forecast_with_profiling(values, prediction_length)

    except Exception as e:
        print(json.dumps({"error": str(e)}))
