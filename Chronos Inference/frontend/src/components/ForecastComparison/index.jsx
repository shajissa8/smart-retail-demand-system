import { useEffect, useState } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  CartesianGrid,
  ResponsiveContainer,
} from "recharts";
import "./index.css"; 

const ForecastComparison = () => {
  const [data, setData] = useState([]);
  const [metrics, setMetrics] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const MAE = (a, b) =>
    a.reduce((sum, v, i) => sum + Math.abs(v - b[i]), 0) / a.length;
  
  const RMSE = (a, b) =>
    Math.sqrt(
      a.reduce((sum, v, i) => sum + Math.pow(v - b[i], 2), 0) / a.length
    );

  useEffect(() => {
    setTimeout(() => {
      const chronos = Array.from({ length: 30 }, (_, i) => 100 + Math.sin(i * 0.3) * 20 + Math.random() * 10);
      const prophet = Array.from({ length: 30 }, (_, i) => 98 + Math.sin(i * 0.3) * 18 + Math.random() * 12);

      const minLen = Math.min(chronos.length, prophet.length);
      const c = chronos.slice(0, minLen).map(Number);
      const p = prophet.slice(0, minLen).map(Number);

      const merged = c.map((v, i) => ({
        day: `Day ${i + 1}`,
        chronos: Number(v.toFixed(2)),
        prophet: Number(p[i].toFixed(2)),
        diff: Number(Math.abs(v - p[i]).toFixed(2)),
      }));

      setData(merged);
      setMetrics({
        mae: MAE(c, p),
        rmse: RMSE(c, p),
        avgChronos: c.reduce((a, b) => a + b, 0) / c.length,
        avgProphet: p.reduce((a, b) => a + b, 0) / p.length,
      });
      setLoading(false);
    }, 500);
  }, []);

  if (loading) {
    return (
      <div className="forecast-loading-container">
        <div className="forecast-loading-content">
          <div className="forecast-loading-spinner"></div>
          <p className="forecast-loading-text">Loading comparison data...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="forecast-error-container">
        <div className="forecast-error-content">
          <div className="forecast-error-icon">⚠️</div>
          <h2 className="forecast-error-title">Error Loading Data</h2>
          <p className="forecast-error-message">{error}</p>
          <button 
            onClick={() => window.location.href = '/forecast'} 
            className="forecast-back-button forecast-error-button"
          >
            ← Back to Forecast
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="forecast-container">
      <div className="forecast-content">
        
        <div className="forecast-header">
          <button 
            onClick={() => window.location.href = '/forecast'} 
            className="forecast-back-button"
          >
            <span>←</span> Back to Forecast
          </button>
          <h1 className="forecast-title">
            Forecast Model Comparison
          </h1>
          <p className="forecast-subtitle">Analyzing Chronos vs Prophet predictions</p>
        </div>

        {/* Chart Section */}
        <div className="forecast-chart-section">
          <h2 className="forecast-section-title">Time Series Forecast</h2>
          <div className="forecast-chart-container">
            <ResponsiveContainer width="100%" height={450}>
              <LineChart data={data} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis 
                  dataKey="day" 
                  stroke="#6b7280"
                  tick={{ fontSize: 12 }}
                />
                <YAxis 
                  stroke="#6b7280"
                  tick={{ fontSize: 12 }}
                />
                <Tooltip 
                  contentStyle={{
                    backgroundColor: 'white',
                    border: '1px solid #e5e7eb',
                    borderRadius: '8px',
                    boxShadow: '0 4px 6px rgba(0,0,0,0.1)'
                  }}
                  formatter={(value) => value.toFixed(2)}
                />
                <Legend 
                  wrapperStyle={{ paddingTop: '20px' }}
                  iconType="line"
                />
                <Line
                  dataKey="chronos"
                  name="Chronos Forecast"
                  stroke="#4f46e5"
                  strokeWidth={3}
                  dot={false}
                  activeDot={{ r: 6 }}
                />
                <Line
                  dataKey="prophet"
                  name="Prophet Forecast"
                  stroke="#10b981"
                  strokeWidth={3}
                  dot={false}
                  activeDot={{ r: 6 }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        {metrics && (
          <div className="forecast-metrics-section">
            <h2 className="forecast-section-title">Performance Metrics</h2>
            
            <div className="forecast-metrics-grid">
              <div className="forecast-metric-card forecast-metric-card-blue">
                <div className="forecast-metric-label">
                  Mean Absolute Error
                </div>
                <div className="forecast-metric-value">
                  {metrics.mae.toFixed(2)}
                </div>
                <div className="forecast-metric-description">
                  Average absolute difference
                </div>
              </div>

              <div className="forecast-metric-card forecast-metric-card-purple">
                <div className="forecast-metric-label">
                  Root Mean Square Error
                </div>
                <div className="forecast-metric-value">
                  {metrics.rmse.toFixed(2)}
                </div>
                <div className="forecast-metric-description">
                  Penalizes large differences
                </div>
              </div>

              <div className="forecast-metric-card forecast-metric-card-green">
                <div className="forecast-metric-label">
                  Chronos Average
                </div>
                <div className="forecast-metric-value">
                  {metrics.avgChronos.toFixed(2)}
                </div>
                <div className="forecast-metric-description">
                  Mean forecast value
                </div>
              </div>

              <div className="forecast-metric-card forecast-metric-card-teal">
                <div className="forecast-metric-label">
                  Prophet Average
                </div>
                <div className="forecast-metric-value">
                  {metrics.avgProphet.toFixed(2)}
                </div>
                <div className="forecast-metric-description">
                  Mean forecast value
                </div>
              </div>
            </div>

            
            <div className="forecast-interpretation">
              <h3 className="forecast-interpretation-title"> Interpretation Guide</h3>
              <ul className="forecast-interpretation-list">
                <li>• <strong>Lower MAE & RMSE</strong> indicate better agreement between models</li>
                <li>• <strong>RMSE &gt; MAE</strong> suggests presence of larger outlier differences</li>
                <li>• Similar averages suggest models predict similar overall trends</li>
              </ul>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default ForecastComparison;
