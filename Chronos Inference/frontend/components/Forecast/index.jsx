import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  LineChart,
  Line,
  CartesianGrid,
  PieChart,
  Pie,
  Cell,
  AreaChart,
  Area,
} from "recharts";
import "./index.css";

/* ─── Custom Tooltip ─────────────────────────────────── */
const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="fc-tooltip">
      <p className="fc-tooltip__label">{label}</p>
      <p className="fc-tooltip__value">
        {payload[0].value.toLocaleString()}
      </p>
    </div>
  );
};

/* ─── Stat Card ──────────────────────────────────────── */
const StatCard = ({ icon, label, value, accent, delay }) => (
  <div className="fc-stat-card" style={{ animationDelay: delay }}>
    <div className={`fc-stat-card__icon fc-stat-card__icon--${accent}`}>
      {icon}
    </div>
    <div className="fc-stat-card__body">
      <span className="fc-stat-card__label">{label}</span>
      <span className="fc-stat-card__value">{value.toLocaleString()}</span>
    </div>
  </div>
);

/* ─── Chart Card ─────────────────────────────────────── */
const ChartCard = ({ title, subtitle, children, delay }) => (
  <div className="fc-chart-card" style={{ animationDelay: delay }}>
    <div className="fc-chart-card__header">
      <h3 className="fc-chart-card__title">{title}</h3>
      {subtitle && (
        <p className="fc-chart-card__subtitle">{subtitle}</p>
      )}
    </div>
    {children}
  </div>
);

/* ─── Constants ──────────────────────────────────────── */
const PALETTE = ["#4f46e5", "#06b6d4", "#f59e0b", "#ef4444", "#8b5cf6", "#10b981"];

/* ─── Main Component ─────────────────────────────────── */
const Forecast = () => {
  const navigate = useNavigate();
  const [selectedPeriod, setSelectedPeriod] = useState("weeks");
  const [displayData, setDisplayData] = useState([]);
  const [summaryStats, setSummaryStats] = useState({});
  const [isLoading, setIsLoading] = useState(true);
  const [hasData, setHasData] = useState(false);
  const [forecastData, setForecastData] = useState([]);

  /* ── Parse localStorage ── */
  useEffect(() => {
    try {
      const raw = localStorage.getItem("forecastData");
      if (!raw) { setHasData(false); return; }

      const parsed = JSON.parse(raw);
      let finalArray = [];

      if (Array.isArray(parsed)) {
        finalArray = parsed;
      } else if (typeof parsed === "object") {
        const firstKey = Object.keys(parsed)[0];
        finalArray = parsed[firstKey] || [];
      }

      if (Array.isArray(finalArray) && finalArray.length > 0) {
        setForecastData(finalArray);
        setHasData(true);
      } else {
        setHasData(false);
      }
    } catch {
      setHasData(false);
    }
  }, []);

  /* ── Process data ── */
  useEffect(() => {
    if (!hasData || forecastData.length === 0) {
      const timer = setTimeout(() => navigate("/home"), 2000);
      return () => clearTimeout(timer);
    }

    let processedData = [];

    if (selectedPeriod === "weeks") {
      processedData = forecastData.map((value, index) => ({
        name: `Wk ${index + 1}`,
        value: Number(parseFloat(value).toFixed(2)),
      }));
    } else {
      for (let i = 0; i < forecastData.length; i += 4) {
        const chunk = forecastData.slice(i, i + 4);
        const sum = chunk.reduce((a, b) => a + parseFloat(b), 0);
        processedData.push({
          name: `Mo ${Math.floor(i / 4) + 1}`,
          value: Number((sum / chunk.length).toFixed(2)),
          total: Number(sum.toFixed(2)),
        });
      }
    }

    const values = processedData.map((d) => d.value);
    const total = values.reduce((a, b) => a + b, 0);

    setSummaryStats({
      total: Number(total.toFixed(2)),
      average: Number((total / values.length).toFixed(2)),
      min: Number(Math.min(...values).toFixed(2)),
      max: Number(Math.max(...values).toFixed(2)),
      periodCount: values.length,
    });

    setDisplayData(processedData);
    setIsLoading(false);
  }, [forecastData, selectedPeriod, hasData, navigate]);

  /* ── Loading / Empty states ── */
  if (isLoading || !hasData) {
    return (
      <div className="fc-splash">
        <div className="fc-spinner" />
        <p className="fc-splash__text">
          {isLoading ? "Loading forecast…" : "No data found. Redirecting…"}
        </p>
      </div>
    );
  }

  const isWeeks = selectedPeriod === "weeks";

  return (
    <div className="fc-root">

      {/* ── Header ── */}
      <header className="fc-header">
        <div className="fc-header__left">
          <h1 className="fc-header__title">
            {isWeeks ? "12-Week" : "3-Month"} Forecast
          </h1>
          <p className="fc-header__subtitle">
            Demand projections · {summaryStats.periodCount} {isWeeks ? "weeks" : "months"}
          </p>
        </div>
        <button className="fc-btn fc-btn--primary" onClick={() => navigate(-1)}>
          ← Back
        </button>
      </header>

      {/* ── Period Toggle ── */}
      <div className="fc-toggle-group">
        {["weeks", "months"].map((p) => (
          <button
            key={p}
            className={`fc-toggle-btn${selectedPeriod === p ? " fc-toggle-btn--active" : ""}`}
            onClick={() => setSelectedPeriod(p)}
          >
            {p.charAt(0).toUpperCase() + p.slice(1)}
          </button>
        ))}
      </div>

      {/* ── Stat Cards ── */}
      <section className="fc-stats">
        <StatCard icon="Σ" label="Total" value={summaryStats.total} accent="indigo" delay="0ms" />
        <StatCard icon="x̄" label="Average" value={summaryStats.average} accent="cyan" delay="60ms" />
        <StatCard icon="↑" label="Peak" value={summaryStats.max} accent="amber" delay="120ms" />
        <StatCard icon="↓" label="Low" value={summaryStats.min} accent="violet" delay="180ms" />
      </section>

      {/* ── Charts ── */}
      <section className="fc-charts">

        <ChartCard title="Volume by period" subtitle="Bar comparison" delay="0ms">
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={displayData} barSize={isWeeks ? 14 : 32}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--fc-grid)" vertical={false} />
              <XAxis dataKey="name" tick={{ fontSize: 12, fill: "var(--fc-text-muted)" }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fontSize: 12, fill: "var(--fc-text-muted)" }} axisLine={false} tickLine={false} width={48} />
              <Tooltip content={<CustomTooltip />} />
              <Bar dataKey="value" fill="#4f46e5" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Trend line" subtitle="Smoothed trajectory" delay="80ms">
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={displayData}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--fc-grid)" vertical={false} />
              <XAxis dataKey="name" tick={{ fontSize: 12, fill: "var(--fc-text-muted)" }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fontSize: 12, fill: "var(--fc-text-muted)" }} axisLine={false} tickLine={false} width={48} />
              <Tooltip content={<CustomTooltip />} />
              <Line
                dataKey="value"
                stroke="#06b6d4"
                strokeWidth={2.5}
                dot={{ r: 4, fill: "#06b6d4", strokeWidth: 0 }}
                activeDot={{ r: 6 }}
              />
            </LineChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Area view" subtitle="Cumulative shape" delay="160ms">
          <ResponsiveContainer width="100%" height={260}>
            <AreaChart data={displayData}>
              <defs>
                <linearGradient id="areaGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#8b5cf6" stopOpacity={0.25} />
                  <stop offset="95%" stopColor="#8b5cf6" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--fc-grid)" vertical={false} />
              <XAxis dataKey="name" tick={{ fontSize: 12, fill: "var(--fc-text-muted)" }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fontSize: 12, fill: "var(--fc-text-muted)" }} axisLine={false} tickLine={false} width={48} />
              <Tooltip content={<CustomTooltip />} />
              <Area
                dataKey="value"
                stroke="#8b5cf6"
                strokeWidth={2.5}
                fill="url(#areaGrad)"
                dot={false}
                activeDot={{ r: 6, fill: "#8b5cf6" }}
              />
            </AreaChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Distribution" subtitle="Period share" delay="240ms">
          <ResponsiveContainer width="100%" height={260}>
            <PieChart>
              <Pie
                data={displayData}
                dataKey="value"
                cx="50%"
                cy="50%"
                innerRadius={55}
                outerRadius={95}
                paddingAngle={2}
              >
                {displayData.map((_, i) => (
                  <Cell key={i} fill={PALETTE[i % PALETTE.length]} />
                ))}
              </Pie>
              <Tooltip content={<CustomTooltip />} />
            </PieChart>
          </ResponsiveContainer>
        </ChartCard>

      </section>

      {/* ── Data Table ── */}
      <section className="fc-table-section">
        <h2 className="fc-table-section__title">Period breakdown</h2>
        <div className="fc-table-wrapper">
          <table className="fc-table">
            <thead>
              <tr>
                <th>Period</th>
                <th>Forecast demand</th>
                <th>vs. average</th>
              </tr>
            </thead>
            <tbody>
              {displayData.map((row, i) => {
                const delta = row.value - summaryStats.average;
                const isUp = delta >= 0;
                return (
                  <tr key={i}>
                    <td className="fc-table__period">{row.name}</td>
                    <td className="fc-table__value">{row.value.toLocaleString()}</td>
                    <td>
                      <span className={`fc-badge fc-badge--${isUp ? "up" : "down"}`}>
                        {isUp ? "+" : ""}{delta.toFixed(1)}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>

    </div>
  );
};

export default Forecast;