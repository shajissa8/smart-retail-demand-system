import { Navigate } from "react-router-dom";

const ProtectedRoute = ({ children, role }) => {
  const token = localStorage.getItem("jwtToken"); // ✅ FIXED
  const userRole = localStorage.getItem("role");

  // No token → login
  if (!token) {
    return <Navigate to="/login" replace />;
  }

  // Role mismatch → block
  if (role && userRole !== role) {
    return <Navigate to="/login" replace />;
  }

  // Access granted
  return children;
};

export default ProtectedRoute;
