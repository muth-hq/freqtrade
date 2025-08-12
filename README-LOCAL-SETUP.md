# Local Freqtrade Setup

This directory contains a local Freqtrade installation that integrates with the Sentimental Monorepo backend.

## Quick Start

### 1. Start Local Freqtrade
```bash
./start-local-freqtrade.sh
```

This will:
- Start Freqtrade in a Docker container
- Enable REST API on `http://localhost:8080`
- Use the configuration in `user_data/config.json`
- Run in dry-run mode by default (safe for testing)

### 2. Verify Connection
```bash
# Test API connection
curl http://localhost:8080/api/v1/ping

# Check bot status (requires auth)
curl -u testuser:testpass123 http://localhost:8080/api/v1/status
```

### 3. Integration with Backend
The Sentimental Monorepo backend is already configured to connect to this local Freqtrade instance:

```bash
# From the backend directory, test integration:
cd ../sentimental-monorepo/apps/backend
deno run --allow-net src/utils/freqtrade-smart-commands.ts status
```

## Configuration

### API Access
- **URL**: `http://localhost:8080`
- **Username**: `testuser`
- **Password**: `testpass123`

### Trading Settings
- **Mode**: Dry run (no real money)
- **Stake**: 10 USDT per trade
- **Max open trades**: 3
- **Pairs**: BTC/USDT, ETH/USDT, ADA/USDT, DOT/USDT, LINK/USDT

### Files Structure
```
freqtrade/
├── start-local-freqtrade.sh        # Startup script
├── docker-compose.local.yml        # Docker configuration
├── user_data/
│   ├── config.json                 # Main configuration
│   └── logs/                       # Log files
└── README-LOCAL-SETUP.md           # This file
```

## Management Commands

### Start/Stop
```bash
# Start
./start-local-freqtrade.sh

# Stop
docker-compose -f docker-compose.local.yml down

# Restart
docker-compose -f docker-compose.local.yml restart
```

### Monitoring
```bash
# View logs
docker logs freqtrade

# Follow logs in real-time
docker logs -f freqtrade

# Check container status
docker ps | grep freqtrade
```

### Configuration Updates
1. Edit `user_data/config.json`
2. Restart the container:
```bash
docker-compose -f docker-compose.local.yml restart
```

## Backend Integration Points

### API Service
- `apps/backend/src/services/integrations/freqtrade-api-service.ts`
- Handles buy/sell signals from sentiment analysis
- Manages trade lifecycle

### Test Scripts
- `apps/backend/src/utils/freqtrade-smart-commands.ts` - Automated trading commands
- `apps/backend/src/utils/freqtrade-manual-commands.ts` - Manual API calls
- `apps/backend/src/utils/test-freqtrade-integration.ts` - Integration testing

## Safety Features

### Dry Run Mode
- No real money is used
- All trades are simulated
- Safe for testing and development

### Risk Management
- Limited stake amount (10 USDT per trade)
- Maximum 3 open trades
- Stop loss and take profit configured

## Troubleshooting

### Connection Issues
```bash
# Check if container is running
docker ps | grep freqtrade

# Check logs for errors
docker logs freqtrade

# Test API endpoint
curl http://localhost:8080/api/v1/ping
```

### Port Conflicts
If port 8080 is in use, edit `docker-compose.local.yml`:
```yaml
ports:
  - "8081:8080"  # Use different external port
```

### Configuration Issues
- Check `user_data/config.json` syntax
- Verify credentials in backend files
- Restart after configuration changes

## Development Workflow

1. **Start Freqtrade**: `./start-local-freqtrade.sh`
2. **Start Backend**: `cd ../sentimental-monorepo && npx nx api backend`
3. **Test Integration**: Run backend test scripts
4. **Monitor**: Check logs and API responses
5. **Iterate**: Update configs and restart as needed

## Production Considerations

To switch to real trading:
1. Set `"dry_run": false` in `user_data/config.json`
2. Add real exchange API keys
3. Adjust risk parameters
4. Enable proper monitoring and alerts

⚠️ **WARNING**: Only disable dry run mode when you're confident in your strategy and risk management!