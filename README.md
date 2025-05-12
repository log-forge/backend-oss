# LogForge backend

## 🔧 Features

- Real-time Docker log streaming via WebSocket
- Smart alert scanning (with keyword-based detection)
- In-memory alert tracking
- API to fetch containers, logs, and alerts
- Endpoint to clear alerts and logs

## 🚀 Quick Start

```bash
git clone https://github.com/log-forge/backend-oss.git
cd backend-oss
docker compose up -d --build
```

## 🧭 API Access

for API endpoints, head to:
```bash
http://localhost:<your_port>/docs
```
By default the port is `8000`.