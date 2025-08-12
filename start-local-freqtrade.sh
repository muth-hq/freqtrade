#!/bin/bash

# Start local Freqtrade with Docker
echo "🚀 Starting local Freqtrade..."
echo "📍 API will be available at http://localhost:8080"
echo "🔑 Username: testuser, Password: testpass123"
echo ""

# Create logs directory if it doesn't exist
mkdir -p user_data/logs

# Start with API server enabled
docker-compose -f docker-compose.local.yml up -d

echo "✅ Freqtrade started successfully!"
echo ""
echo "📊 To check status: docker logs freqtrade"
echo "🛑 To stop: docker-compose -f docker-compose.local.yml down"
echo ""
echo "🔧 Configuration file: user_data/config.json"
echo "📝 Logs: user_data/logs/freqtrade.log"