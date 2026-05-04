import { Component } from "react";
import { Navigate } from "react-router-dom";
import "./index.css";

class Login extends Component {
  state = {
    username: "",
    password: "",
    name: "",
    gender: "Male",
    error: "",
    redirect: false,
    role: "",
    isRegister: false,
  };

  handleLogin = async (e) => {
    e.preventDefault();
    try {
      const res = await fetch("http://localhost:3000/login/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: this.state.username,
          password: this.state.password,
        }),
      });

      const data = await res.json();

      if (!res.ok) {
        this.setState({ error: data.error || "Invalid username or password" });
      } else {
        // ✅ FIX: correct key name
        localStorage.setItem("jwtToken", data.jwtToken);
        localStorage.setItem("role", data.role);

        this.setState({
          redirect: true,
          role: data.role,
          error: "",
        });
      }
    } catch (err) {
      this.setState({ error: "Server error" });
    }
  };

  handleRegister = async (e) => {
    e.preventDefault();
    try {
      const res = await fetch("http://localhost:3000/register/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: this.state.username,
          password: this.state.password,
          name: this.state.name,
          gender: this.state.gender,
        }),
      });

      const text = await res.text();

      if (!res.ok) {
        this.setState({ error: text });
      } else {
        alert("Registration successful! Please log in.");
        this.setState({
          isRegister: false,
          error: "",
          password: "",
        });
      }
    } catch (err) {
      this.setState({ error: "Server error" });
    }
  };

  toggleForm = () => {
    this.setState({
      isRegister: !this.state.isRegister,
      error: "",
      username: "",
      password: "",
      name: "",
      gender: "Male",
    });
  };

  render() {
    if (this.state.redirect) {
      return (
        <Navigate
          to={this.state.role === "admin" ? "/admin" : "/home"}
          replace
        />
      );
    }

    return (
      <form
        onSubmit={
          this.state.isRegister ? this.handleRegister : this.handleLogin
        }
      >
        <div className="heading-container">
          <h1 className="heading">
            {this.state.isRegister ? "Register" : "Log In"}
          </h1>
        </div>

        {this.state.isRegister && (
          <>
            <input
              placeholder="Name"
              value={this.state.name}
              onChange={(e) => this.setState({ name: e.target.value })}
              required
            />

            <select
              value={this.state.gender}
              onChange={(e) => this.setState({ gender: e.target.value })}
            >
              <option value="Male">Male</option>
              <option value="Female">Female</option>
              <option value="Other">Other</option>
            </select>
          </>
        )}

        <input
          placeholder="Username"
          value={this.state.username}
          onChange={(e) => this.setState({ username: e.target.value })}
          required
        />

        <input
          type="password"
          placeholder="Password"
          value={this.state.password}
          onChange={(e) => this.setState({ password: e.target.value })}
          required
        />

        <button type="submit" className="login-btn">
          {this.state.isRegister ? "Register" : "Login"}
        </button>

        {this.state.error && <p className="error-text">{this.state.error}</p>}

        <p onClick={this.toggleForm} className="toggle-text">
          {this.state.isRegister
            ? "Already have an account? Log In"
            : "Don't have an account? Register"}
        </p>
      </form>
    );
  }
}

export default Login;
