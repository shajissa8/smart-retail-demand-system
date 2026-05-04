// Admin.jsx
import React, { useState, useEffect } from 'react';
import './index.css';

const Admin = () => {
  const [animateStats, setAnimateStats] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [filterRole, setFilterRole] = useState('all');

  useEffect(() => {
    setAnimateStats(true);
  }, []);

  const users = [
    { username: 'john', name: 'John Doe', role: 'User', status: 'Active' },
    { username: 'admin', name: 'System Admin', role: 'Admin', status: 'Active' },
    { username: 'mary', name: 'Mary Smith', role: 'User', status: 'Inactive' },
    { username: 'sarah', name: 'Sarah Johnson', role: 'User', status: 'Active' },
    { username: 'mike', name: 'Mike Wilson', role: 'Manager', status: 'Active' },
  ];

  const filteredUsers = users.filter(user => {
    const matchesSearch = user.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         user.username.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesRole = filterRole === 'all' || user.role.toLowerCase() === filterRole.toLowerCase();
    return matchesSearch && matchesRole;
  });

  return (
    <div className="admin-container">
      {/* Header */}
      <header className="admin-header">
        <div className="header-content">
          <div className="header-left">
            <h1 className="header-title">Retail Demand Forecasting</h1>
            <p className="header-subtitle">Admin Dashboard</p>
          </div>
          <button className="logout-btn">Logout</button>
        </div>
      </header>

      {/* Main Content */}
      <main className="admin-main">
        {/* Welcome Banner */}
        <div className="welcome-banner">
          <h2 className="banner-title">Welcome Back, Admin! 👋</h2>
        </div>

        {/* Stats Grid */}
        <div className="stats-grid">
          <div className={`stat-card stat-card-1 ${animateStats ? 'animate' : ''}`}>
            <div className="stat-icon stat-icon-purple">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/>
                <circle cx="9" cy="7" r="4"/>
                <path d="M22 21v-2a4 4 0 0 0-3-3.87"/>
                <path d="M16 3.13a4 4 0 0 1 0 7.75"/>
              </svg>
            </div>
            <h3 className="stat-label">Total Users</h3>
            <p className="stat-value">10</p>
          </div>

          <div className={`stat-card stat-card-2 ${animateStats ? 'animate' : ''}`}>
            <div className="stat-icon stat-icon-green">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
              </svg>
            </div>
            <h3 className="stat-label">Active Users</h3>
            <p className="stat-value">8</p>
          </div>

          <div className={`stat-card stat-card-3 ${animateStats ? 'animate' : ''}`}>
            <div className="stat-icon stat-icon-blue">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <line x1="12" y1="20" x2="12" y2="10"/>
                <line x1="18" y1="20" x2="18" y2="4"/>
                <line x1="6" y1="20" x2="6" y2="16"/>
              </svg>
            </div>
            <h3 className="stat-label">Forecast Requests</h3>
            <p className="stat-value">24</p>
          </div>

          <div className={`stat-card stat-card-4 ${animateStats ? 'animate' : ''}`}>
            <div className="stat-icon stat-icon-orange">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/>
                <polyline points="17 6 23 6 23 12"/>
              </svg>
            </div>
            <h3 className="stat-label">System Status</h3>
            <p className="stat-value">Online</p>
          </div>
        </div>

        <div className="content-grid">
          {/* User Management */}
          <div className="user-management-section">
            <div className="section-card">
              <div className="section-header">
                <h2 className="section-title">User Management</h2>
                <button className="export-btn">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                    <polyline points="7 10 12 15 17 10"/>
                    <line x1="12" y1="15" x2="12" y2="3"/>
                  </svg>
                  Export
                </button>
              </div>

              {/* Search and Filter */}
              <div className="filter-controls">
                <div className="search-box">
                  <svg className="search-icon" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <circle cx="11" cy="11" r="8"/>
                    <path d="m21 21-4.35-4.35"/>
                  </svg>
                  <input
                    type="text"
                    placeholder="Search users..."
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                    className="search-input"
                  />
                </div>
                <div className="filter-box">
                  <svg className="filter-icon" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"/>
                  </svg>
                  <select
                    value={filterRole}
                    onChange={(e) => setFilterRole(e.target.value)}
                    className="filter-select"
                  >
                    <option value="all">All Roles</option>
                    <option value="user">User</option>
                    <option value="admin">Admin</option>
                    <option value="manager">Manager</option>
                  </select>
                </div>
              </div>

              {/* User Table */}
              <div className="table-container">
                <table className="user-table">
                  <thead>
                    <tr>
                      <th>Username</th>
                      <th>Name</th>
                      <th>Role</th>
                      <th>Status</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredUsers.map((user, index) => (
                      <tr key={index} className="table-row" style={{ animationDelay: `${index * 0.1}s` }}>
                        <td className="td-username">{user.username}</td>
                        <td className="td-name">{user.name}</td>
                        <td>
                          <span className={`badge badge-${user.role.toLowerCase()}`}>
                            {user.role}
                          </span>
                        </td>
                        <td>
                          <span className={`badge badge-${user.status.toLowerCase()}`}>
                            {user.status}
                          </span>
                        </td>
                        <td>
                          <div className="action-buttons">
                            {user.role !== 'Admin' && (
                              <>
                                {user.status === 'Active' ? (
                                  <>
                                    <button className="btn btn-admin">Make Admin</button>
                                    <button className="btn btn-disable">Disable</button>
                                  </>
                                ) : (
                                  <button className="btn btn-activate">Activate</button>
                                )}
                              </>
                            )}
                            {user.role === 'Admin' && (
                              <button className="btn btn-protected" disabled>Protected</button>
                            )}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          {/* Forecast Overview */}
          <div className="forecast-section">
            <div className="section-card">
              <h2 className="section-title">Forecast Overview</h2>
              
              <div className="forecast-stats">
                <div className="forecast-stat-card forecast-stat-1">
                  <p className="forecast-label">Total Forecasts</p>
                  <p className="forecast-value">30</p>
                </div>
                
                <div className="forecast-stat-card forecast-stat-2">
                  <p className="forecast-label">Last Forecast</p>
                  <p className="forecast-value-small">2 hours ago</p>
                </div>

                <div className="forecast-stat-card forecast-stat-3">
                  <p className="forecast-label">Accuracy Rate</p>
                  <p className="forecast-value">94.2%</p>
                </div>
              </div>

              <button className="history-btn">View Forecast History</button>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
};

export default Admin;