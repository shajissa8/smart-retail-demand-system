import React, { Component } from "react";
import { Navigate } from "react-router-dom"; // ADD THIS IMPORT
import Header from "../Header";
import "./index.css";

class Home extends Component {
  constructor(props) {
    super(props);
    this.state = {
      floatingElements: [],
      selectedFile: null,
      loading: false,
      shouldRedirect: false
    };

    this.features = [
      { icon: "1", title: "Real-Time Processing", text: "Get instant insights from your data with our powerful AI engine" },
      { icon: "2", title: "Accurate Predictions", text: "95% forecast accuracy powered by advanced machine learning" },
      { icon: "3", title: "Multi-Platform", text: "Access your dashboard anywhere, anytime on any device" }
    ];

    this.footerLinks = {
      Product: ["Features", "Pricing", "API", "Documentation"],
      Company: ["About Us", "Careers", "Blog", "Contact"],
      Legal: ["Privacy Policy", "Terms of Service", "Cookie Policy", "Compliance"]
    };
  }

  componentDidMount() {
    const elements = Array.from({ length: 6 }, (_, i) => ({
      id: i,
      left: Math.random() * 100,
      delay: Math.random() * 5,
      duration: 15 + Math.random() * 10
    }));
    this.setState({ floatingElements: elements });
  }

  handleFileChange = (event) => {
    this.setState({ selectedFile: event.target.files[0] });
  };

  uploadAndForecast = async () => {
  if (!this.state.selectedFile) {
    alert("Please select a CSV file");
    return;
  }

  this.setState({ loading: true });

  const token = localStorage.getItem("jwtToken");
  const formData = new FormData();
  formData.append("file", this.state.selectedFile);

  try {
    const response = await fetch("http://localhost:3000/forecast/", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
      },
      body: formData,
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.error || "Forecast failed");
    }

    const data = await response.json();

    /* ===============================
       STORE CHRONOS FORECAST
    =============================== */
    const chronosForecast = data.chronos || data.predictions;

    localStorage.setItem(
      "forecastData",
      JSON.stringify(chronosForecast)
    );
    localStorage.setItem("prophetForecastData", JSON.stringify(data.prophet));
    localStorage.setItem("comparisonData", JSON.stringify({chronos: chronosForecast, prophet: data.prophet}));
    if (data.prophet && Array.isArray(data.prophet)) {
      localStorage.setItem(
      "prophetForecast",
      JSON.stringify(data.prophet)
    );

  localStorage.setItem(
    "comparisonData",
    JSON.stringify({
      chronos: chronosForecast,
      prophet: data.prophet,
    })
  );
}


    this.setState({ loading: false, shouldRedirect: true });

  } catch (error) {
    console.error("Forecast failed:", error.message);
    alert(`Forecast failed: ${error.message}`);
    this.setState({ loading: false });
  }
};



  renderFeatures() {
    return this.features.map((feature, index) => (
      <div key={index} className="info-card">
        <div className="info-icon">{feature.icon}</div>
        <h3 className="info-title">{feature.title}</h3>
        <p className="info-text">{feature.text}</p>
      </div>
    ));
  }

  renderFooterLinks() {
    return Object.entries(this.footerLinks).map(([title, links]) => (
      <div key={title} className="footer-section">
        <h4 className="footer-heading">{title}</h4>
        <ul className="footer-list">
          {links.map((link, i) => (
            <li key={i} className="footer-list-item">
              <a href="#" className="footer-link">{link}</a>
            </li>
          ))}
        </ul>
      </div>
    ));
  }

  renderSocialIcons() {
    return ["📘", "🐦", "💼", "📧"].map((icon, i) => (
      <a key={i} href="#" className="social-icon">{icon}</a>
    ));
  }

  render() {
    const { loading, shouldRedirect } = this.state;

    // FIXED: Now using the properly imported Navigate
    if (shouldRedirect) {
      return <Navigate to="/forecast" />;
    }

    return (
      <>
        <Header />
        <div className="container">
          <div className="home">
            <div className="hero">
              <div className="badge">AI-Powered Analytics</div>
              <h1 className="title">Demand Forecast Dashboard</h1>
              <p className="subtitle">
                Upload recent sales data, analyze AI-powered forecasts, and track
                social media trends impacting demand.
              </p>

              <div className="button-group">
                <input
                  type="file"
                  accept=".csv"
                  onChange={this.handleFileChange}
                />

                <button
                  className="primary-button"
                  onClick={this.uploadAndForecast}
                >
                  {loading ? "Processing..." : "Upload Data"}
                </button>

                <button className="secondary-button">
                  View Demo <span className="button-icon">▶</span>
                </button>
              </div>
            </div>

            <div className="info-section">
              {this.renderFeatures()}
            </div>
          </div>

          <footer className="footer">
            <div className="footer-content">
              <div className="footer-section">
                <h3 className="footer-title">Forecast Platform</h3>
                <p className="footer-text">
                  Empowering businesses with AI-driven demand forecasting and analytics.
                </p>
                <div className="social-links">
                  {this.renderSocialIcons()}
                </div>
              </div>

              {this.renderFooterLinks()}
            </div>

            <div className="footer-bottom">
              <p className="copyright">
                © 2024 Forecast Platform. All rights reserved.
              </p>
            </div>
          </footer>
        </div>
      </>
    );
  }
}

export default Home;
