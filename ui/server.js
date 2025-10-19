const express = require('express');
const axios = require('axios');
const cors = require('cors');
const path = require('path');

const app = express();
const port = process.env.PORT || 3000;
const apiUrl = process.env.API_URL || 'http://localhost:8000';

app.use(cors());
app.use(express.json());
app.use(express.static(path.join(__dirname, 'public')));

// Proxy API requests
app.get('/api/*', async (req, res) => {
  try {
    const response = await axios.get(`${apiUrl}${req.path.replace('/api', '')}`);
    res.json(response.data);
  } catch (error) {
    res.status(500).json({ error: 'API request failed' });
  }
});

// Serve main page
app.get('/', (req, res) => {
  res.send(`
    <!DOCTYPE html>
    <html>
    <head>
        <title>Lab AI</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; }
            .container { max-width: 800px; margin: 0 auto; }
            .service { margin: 20px 0; padding: 15px; border: 1px solid #ddd; border-radius: 5px; }
            .status { padding: 5px 10px; border-radius: 3px; color: white; }
            .healthy { background-color: green; }
            .unhealthy { background-color: red; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Lab AI Dashboard</h1>
            <div class="service">
                <h3>API Service</h3>
                <p>Status: <span id="api-status" class="status">Checking...</span></p>
            </div>
            <div class="service">
                <h3>Services</h3>
                <ul>
                    <li><a href="http://localhost:8080" target="_blank">Label Studio</a> - Data labeling platform</li>
                    <li><a href="http://localhost:8081" target="_blank">Airflow</a> - Workflow orchestration (admin/admin)</li>
                </ul>
            </div>
        </div>
        <script>
            fetch('/api/health')
                .then(response => response.json())
                .then(data => {
                    const status = document.getElementById('api-status');
                    if (data.status === 'healthy') {
                        status.textContent = 'Healthy';
                        status.className = 'status healthy';
                    } else {
                        status.textContent = 'Unhealthy';
                        status.className = 'status unhealthy';
                    }
                })
                .catch(() => {
                    const status = document.getElementById('api-status');
                    status.textContent = 'Offline';
                    status.className = 'status unhealthy';
                });
        </script>
    </body>
    </html>
  `);
});

app.listen(port, '0.0.0.0', () => {
  console.log(`Lab AI UI running on port ${port}`);
});