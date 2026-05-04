const express = require("express");
const path = require("path");
const cors = require("cors");
const { open } = require("sqlite");
const sqlite3 = require("sqlite3");
const bcrypt = require("bcrypt");
const jwt = require("jsonwebtoken");
const multer = require("multer");
const fs = require("fs");
const axios = require("axios");
const csvParse = require("csv-parse/sync");
const { execFile } = require("child_process");
require("dotenv").config();

const app = express();

/* ---------- MIDDLEWARES ---------- */
app.use(express.json());

app.use(
  cors({
    origin: "http://localhost:5173",
    methods: ["GET", "POST", "PUT", "DELETE"],
    allowedHeaders: ["Content-Type", "Authorization"],
  })
);

/* ---------- FILE UPLOAD ---------- */
const upload = multer({
  dest: "uploads/",
  limits: { fileSize: 5 * 1024 * 1024 },
});

/* ---------- DATABASE ---------- */
let db = null;
const dbPath = path.join(__dirname, "db", "app.db");

const initializeDbAndServer = async () => {
  try {
    db = await open({
      filename: dbPath,
      driver: sqlite3.Database,
    });

    await db.run(`
      CREATE TABLE IF NOT EXISTS user (
        user_id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT,
        name TEXT,
        gender TEXT,
        role TEXT DEFAULT 'user'
      );
    `);

    app.listen(3000, () => {
      console.log("🚀 Server running at http://localhost:3000");
    });
  } catch (e) {
    console.error(`DB Error: ${e.message}`);
    process.exit(1);
  }
};

initializeDbAndServer();

/* ---------- AUTH MIDDLEWARE ---------- */
const authenticateToken = (request, response, next) => {
  const authHeader = request.headers["authorization"];
  const token = authHeader && authHeader.split(" ")[1];

  if (!token) {
    return response.status(401).json({ error: "Invalid JWT Token" });
  }

  jwt.verify(token, "ABCDEF", (error, payload) => {
    if (error) {
      return response.status(401).json({ error: "Invalid JWT Token" });
    }
    request.userId = payload.userId;
    request.role = payload.role;
    next();
  });
};

/* ---------- AUTH ROUTES ---------- */

// Register
app.post("/register/", async (request, response) => {
  const { username, password, name, gender } = request.body;

  const user = await db.get(
    `SELECT * FROM user WHERE username = ?`,
    [username]
  );

  if (user) {
    response.status(400).send("User already exists");
  } else if (password.length < 6) {
    response.status(400).send("Password is too short");
  } else {
    const hashedPassword = await bcrypt.hash(password, 10);
    await db.run(
      `INSERT INTO user (username, password, name, gender)
       VALUES (?, ?, ?, ?)`,
      [username, hashedPassword, name, gender]
    );
    response.send("User created successfully");
  }
});

// Login
app.post("/login/", async (request, response) => {
  const { username, password } = request.body;

  const user = await db.get(
    `SELECT * FROM user WHERE username = ?`,
    [username]
  );

  if (!user) {
    return response.status(400).json({ error: "Invalid username" });
  }

  const isPasswordMatched = await bcrypt.compare(password, user.password);

  if (!isPasswordMatched) {
    return response.status(400).json({ error: "Invalid password" });
  }

  const payload = {
    userId: user.user_id,
    role: user.role,
  };

  const jwtToken = jwt.sign(payload, "ABCDEF", {
    expiresIn: "1h",
  });

  response.json({ jwtToken, role: user.role });
});

// Profile
app.get("/profile/", authenticateToken, async (request, response) => {
  const user = await db.get(
    `SELECT username, name, gender, role FROM user WHERE user_id = ?`,
    [request.userId]
  );
  response.send(user);
});

/* ---------- FORECAST API ---------- */

app.post(
  "/forecast",
  authenticateToken,
  upload.single("file"),
  async (req, res) => {
    try {
      if (!req.file) {
        return res.status(400).json({ error: "CSV file required" });
      }

      const csvPath = req.file.path;

      /* 🔍 AUTO-DETECT COLUMNS */
      const csvData = fs.readFileSync(csvPath);
      const records = csvParse.parse(csvData, {
        columns: true,
        skip_empty_lines: true,
      });

      if (!records || records.length === 0) {
        return res.status(400).json({ error: "Empty CSV file" });
      }

      const columns = Object.keys(records[0]);

      // Auto-detect date column
      const date_col =
        columns.find(c => 
          c.toLowerCase().includes("date") || 
          c.toLowerCase().includes("time") ||
          c.toLowerCase().includes("day")
        ) || columns[0];

      // Auto-detect target column (sales/demand/value)
      const target_col =
        columns.find(c =>
          c.toLowerCase().includes("sales") ||
          c.toLowerCase().includes("demand") ||
          c.toLowerCase().includes("value") ||
          c.toLowerCase().includes("quantity") ||
          c.toLowerCase().includes("units")
        ) || columns[1];

      // Auto-detect ID columns
      const id_cols = columns.filter(c =>
        c.toLowerCase().includes("id") ||
        c.toLowerCase().includes("store") ||
        c.toLowerCase().includes("product") ||
        c.toLowerCase().includes("sku")
      );

      const freq = "D"; // Default daily

      const preprocessScript = path.join(
        __dirname,
        "..",
        "ml",
        "preprocess_service.py"
      );

      /* 🐍 CALL PYTHON PREPROCESSOR */
      execFile(
        "python",
        [preprocessScript, csvPath],
        async (error, stdout, stderr) => {

          try {

            if (error) {
              console.error("Python preprocessor error:", stderr || error.message);

              if (fs.existsSync(csvPath)) {
                fs.unlinkSync(csvPath);
              }

              return res.status(500).json({ error: "Preprocessing failed" });
            }

            console.log("========== UPDATED PYTHON STDOUT ==========");
            console.log(stdout);
            console.log("========================================");

            const seriesDict = JSON.parse(stdout.trim());
            const storeId = Object.keys(seriesDict)[0];
            const values = seriesDict[storeId];

            const mlResponse = await axios.post(
              "http://127.0.0.1:5001/predict",
              {
                values: [values],
                prediction_length: 12,
              },
              { timeout: 300000 }
            );

            const forecasts = {
              [storeId]: mlResponse.data.nudged || []
            };

            if (fs.existsSync(csvPath)) {
              fs.unlinkSync(csvPath);
            }

            return res.json({
              chronos: forecasts,
              predictions: forecasts,
              prophet: []
            });

          } catch (err) {

            console.error("Forecast processing error:", err);

            if (fs.existsSync(csvPath)) {
              fs.unlinkSync(csvPath);
            }

            return res.status(500).json({
              error: "Forecast failed: " + err.message
            });
          }
        }
      );
    } catch (err) {
      console.error("Forecast route error:", err);

      if (req.file && fs.existsSync(req.file.path)) {
        fs.unlinkSync(req.file.path);
      }

      return res.status(500).json({
        error: "Forecast failed: " + err.message
      });
    }
  }
);

/* ---------- CSV COLUMN INSPECTION ---------- */

app.post("/dataset/columns", upload.single("file"), async (req, res) => {
  try {
    if (!req.file) {
      return res.status(400).json({ error: "CSV file required" });
    }

    const csvFilePath = req.file.path;
    const csvData = fs.readFileSync(csvFilePath);
    const records = csvParse.parse(csvData, {
      columns: true,
      skip_empty_lines: true,
    });

    // Clean up file after reading
    fs.unlinkSync(csvFilePath);

    res.json({ 
      columns: Object.keys(records[0]),
      rowCount: records.length 
    });
  } catch (error) {
    console.error("Column inspection error:", error);
    res.status(500).json({ error: "Failed to read columns" });
  }
});

/* ---------- HEALTH CHECK ---------- */
app.get("/health", (req, res) => {
  res.json({ status: "OK", timestamp: new Date().toISOString() });
});

module.exports = app;
