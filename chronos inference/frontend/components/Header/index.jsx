import { Component } from 'react';
import './index.css';

class Header extends Component {
  logout = () => {
    localStorage.clear();
    window.location.href = "/login";
  };

  render() {
    return (
      <header className ="app-header">
        <h3 className = "header-heading">Retail Demand Forecasting</h3>
        <button className ="logout-btn" onClick={this.logout}>Logout</button>
      </header>
    );
  }
}

export default Header;
